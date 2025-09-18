"""
FastMCP v2.12.3 server with Okta OAuth2 using RemoteAuthProvider.

This implementation uses FastMCP's RemoteAuthProvider which is perfect for
Single Page Apps (SPAs) that use JWT token verification without client secrets.
"""

import os
import json
from pathlib import Path
from fastmcp.server.auth import RemoteAuthProvider, JWTVerifier
from starlette.responses import JSONResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Import the base server
try:
    from .server import mcp as base_mcp
except ImportError:
    from src.odoo_mcp.server import mcp as base_mcp

def load_config():
    """Load configuration from fastmcp.json if available."""

    current_dir = Path(__file__).parent

    # Try multiple possible locations
    possible_paths = [
        Path("fastmcp.json"), 
        current_dir / "../../fastmcp.json", 
        current_dir.parent.parent / "fastmcp.json",
    ]

    for config_path in possible_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                continue

    print("⚠️  No configuration found, using defaults.")
    return {}

# Load configuration from fastmcp.json
config = load_config()
auth_config = config.get("auth", {})
environment_config = config.get("environment", {})

# Get OAuth configuration from config file first, then fallback to environment variables
jwks_uri = environment_config.get("FASTMCP_AUTH_JWKS_URI") or os.getenv("FASTMCP_AUTH_JWKS_URI")
issuer = environment_config.get("FASTMCP_AUTH_ISSUER") or os.getenv("FASTMCP_AUTH_ISSUER")
audience = environment_config.get("FASTMCP_AUTH_AUDIENCE") or os.getenv("FASTMCP_AUTH_AUDIENCE")
client_id = environment_config.get("FASTMCP_AUTH_CLIENT_ID") or os.getenv("FASTMCP_AUTH_CLIENT_ID")

# Extract base Okta URL for endpoints that don't need /oauth2/default
okta_base_url = issuer.replace("/oauth2/default", "") if issuer else None

# Check if OAuth is configured (no client secret needed for SPA)
auth_configured = all([jwks_uri, issuer, audience])

if auth_configured:
    base_url = auth_config.get("base_url", "http://localhost:8000")

    # Create JWT token verifier for SPA applications
    token_verifier = JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=audience
    )

    # Create Remote Auth Provider for SPA applications
    # RemoteAuthProvider is perfect for SPAs as it only handles JWT verification
    # without requiring client secrets or OAuth flow management
    auth_provider = RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[issuer],
        base_url=base_url
    )

    print("🔒 Okta OAuth Provider configured")
    print(f"  JWKS URI: {jwks_uri}")
    print(f"  Issuer: {issuer}")
    print(f"  Base URL: {base_url}")

    # Add auth to the existing server
    # FastMCP will automatically handle:
    # - JWT token verification
    # - Authorization server metadata endpoints
    # - CORS for protected resources
    base_mcp.auth = auth_provider

    # Helper function to add CORS headers to all .well-known endpoints
    def add_cors_headers(response):
        """Add CORS headers for Inspector tool compatibility"""
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

    # Helper function to generate OAuth authorization server metadata
    def get_oauth_server_metadata():
        """Generate OAuth Authorization Server Metadata (RFC 8414)"""
        return {
            "issuer": issuer,  # Use actual Okta issuer for proper DCR discovery
            "authorization_endpoint": f"{issuer}/v1/authorize",
            "token_endpoint": f"{issuer}/v1/token",
            "jwks_uri": jwks_uri,
            "registration_endpoint": f"{base_url}/oauth2/default/v1/clients",  # Point to our DCR endpoint
            "scopes_supported": ["openid", "profile", "email"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            "code_challenge_methods_supported": ["S256"],
            "introspection_endpoint": f"{issuer}/v1/introspect",
            "revocation_endpoint": f"{issuer}/v1/revoke"
        }

    # Add missing OAuth discovery endpoints that RemoteAuthProvider doesn't provide
    @base_mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def oauth_authorization_server(request):
        """OAuth Authorization Server Metadata (RFC 8414)"""
        response = JSONResponse(get_oauth_server_metadata())
        return add_cors_headers(response)

    @base_mcp.custom_route("/.well-known/oauth-authorization-server/mcp", methods=["GET", "OPTIONS"])
    async def oauth_authorization_server_mcp(request):
        """OAuth Authorization Server Metadata for MCP (RFC 8414)"""
        response = JSONResponse(get_oauth_server_metadata())
        return add_cors_headers(response)

    @base_mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET", "OPTIONS"])
    async def oauth_protected_resource_mcp(request):
        """OAuth Protected Resource Metadata for MCP endpoint"""
        response = JSONResponse({
            "resource": f"{base_url}/mcp",
            "authorization_servers": [base_url],  # Use MCP server as auth server for discovery
            "scopes_required": ["mcp:access"],
            "bearer_methods_supported": ["header"]
        })
        return add_cors_headers(response)

    @base_mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def oauth_protected_resource(request):
        """OAuth Protected Resource Metadata for MCP endpoint"""
        print("Fetching OAuth Protected Resource Metadata")
        response = JSONResponse({
            "resource": f"{base_url}/mcp",
            "authorization_servers": [base_url],  # Use MCP server as auth server for discovery
            "scopes_required": ["mcp:access"],
            "bearer_methods_supported": ["header"]
        })
        return add_cors_headers(response)

    @base_mcp.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def openid_configuration(request):
        """Redirect to Okta's OpenID Connect configuration"""
        response = RedirectResponse(url=f"{issuer}/.well-known/openid-configuration", status_code=302)
        return add_cors_headers(response)

    @base_mcp.custom_route("/oauth2/default/v1/clients", methods=["POST", "OPTIONS"])
    async def dynamic_client_registration(request):
        """Dynamic Client Registration endpoint - returns static Okta client config"""
        print(f"🔍 DCR Request from {request.client.host}")
        print(f"🔍 Method: {request.method}")
        print(f"🔍 Configured client_id: {client_id}")

        if client_id:
            dcr_response = {
                "client_id": client_id,
                "client_secret": "",  # Public client, no secret needed
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                "application_type": "web",
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",  # Public client
                "scope": "openid profile email"
            }
            print(f"✅ DCR Response: {dcr_response}")
            response = JSONResponse(dcr_response)
        else:
            print("❌ client_id not configured!")
            response = JSONResponse({"error": "client_id not configured"}, status_code=500)
        return add_cors_headers(response)

    @base_mcp.custom_route("/register", methods=["POST", "OPTIONS"])
    async def register_client(request):
        """Dynamic Client Registration endpoint - returns static Okta client config"""
        response = JSONResponse(
            {
                "client_id": client_id
            },
            status_code=201,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*"
            }
        )
        return add_cors_headers(response)    

else:
    print("⚠️  OAuth not configured. Configure in fastmcp.json or set environment variables:")
    print("   FASTMCP_AUTH_JWKS_URI")
    print("   FASTMCP_AUTH_ISSUER")
    print("   FASTMCP_AUTH_AUDIENCE")
    print("   (No client secret needed for SPA applications)")
    print("   Config file location checked: fastmcp.json")

# Export the server (with or without auth)
mcp = base_mcp