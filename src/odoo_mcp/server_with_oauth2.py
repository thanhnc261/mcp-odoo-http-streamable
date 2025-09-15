"""
Example integration of OAuth2 authentication with the existing MCP server.

This file demonstrates how to integrate OAuth2 authentication into the 
existing Odoo MCP server using the new auth module.
"""

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from urllib.parse import urlencode

from .odoo_client import OdooClient, get_odoo_client
from .extensions import register_all_extensions
from .auth import (
    AuthenticationSettings,
    OAuth2DiscoveryService,
    create_discovery_service,
    get_protected_resource_metadata_handler,
    get_authorization_server_metadata_handler,
    register_client_handler
)
from .auth.session import session_manager
import threading
import time


@dataclass
class AppContext:
    """Application context for the MCP server with OAuth2 integration"""
    
    odoo: OdooClient
    discovery_service: Optional[OAuth2DiscoveryService] = None


@asynccontextmanager
async def app_lifespan_with_oauth2(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Application lifespan with OAuth2 initialization
    """
    # Initialize Odoo client
    odoo_client = get_odoo_client()
    
    # Initialize OAuth2 discovery service
    from .auth.settings import load_auth_config_from_file
    config_data = load_auth_config_from_file("auth_config.json")
    auth_settings = AuthenticationSettings(**config_data)
    discovery_service = create_discovery_service(auth_settings, "http://localhost:8000")
    
    try:
        yield AppContext(
            odoo=odoo_client, 
            discovery_service=discovery_service
        )
    finally:
        # No cleanup needed
        pass


def create_oauth2_enabled_server(config_file: Optional[str] = None) -> FastMCP:
    """
    Create MCP server with OAuth2 authentication enabled.
    
    Args:
        config_file: Path to auth configuration file (defaults to auth_config.json)
    
    This function demonstrates how to integrate OAuth2 into the existing server.
    """
    from mcp.server.auth.settings import AuthSettings
    from .auth.factory import create_token_verifier
    
    # Load authentication settings
    from .auth.settings import load_auth_config_from_file
    config_data = load_auth_config_from_file(config_file or "auth_config.json")
    auth_settings_data = AuthenticationSettings(**config_data)
    
    # Create MCP SDK AuthSettings for FastMCP
    mcp_auth_settings = AuthSettings(
        issuer_url=f"https://trial-2386786.okta.com/oauth2/default",  # Authorization server URL
        resource_server_url="http://localhost:8000",  # Our MCP server URL
        required_scopes=["mcp:access"],  # Required scopes for MCP access
    )
    
    # Create token verifier using our existing Okta provider
    token_verifier = create_token_verifier(auth_settings_data)
    
    # Create MCP server with authentication enabled
    mcp = FastMCP(
        name="Odoo MCP Server with OAuth2",
        dependencies=["requests", "httpx", "pyjwt", "pydantic"],
        auth=mcp_auth_settings,
        token_verifier=token_verifier,
        lifespan=app_lifespan_with_oauth2,
    )
    
    # Register existing resources and tools
    register_existing_endpoints(mcp)
    
    # Register OAuth2 discovery endpoints
    register_discovery_endpoints(mcp)
    
    # Register OAuth2 client registration tool
    register_client_tool(mcp)
    
    # Skip adding duplicate HTTP discovery routes - using FastMCP routes instead
    # setup_http_discovery_routes(mcp)
    
    # Register all extensions
    register_all_extensions(mcp)
    
    return mcp


def register_existing_endpoints(mcp: FastMCP):
    """Register existing endpoints (can be protected or unprotected)"""
    
    @mcp.resource(
        "odoo://models", 
        description="List all available models in the Odoo system"
    )
    def get_models() -> str:
        """Lists all available models in the Odoo system"""
        odoo_client = get_odoo_client()
        models = odoo_client.get_models()
        return json.dumps(models, indent=2)
    
    @mcp.resource(
        "odoo://model/{model_name}",
        description="Get detailed information about a specific model"
    )
    def get_model_info(model_name: str) -> str:
        """Get information about a specific model"""
        odoo_client = get_odoo_client()
        try:
            model_info = odoo_client.get_model_info(model_name)
            fields = odoo_client.get_model_fields(model_name)
            model_info["fields"] = fields
            return json.dumps(model_info, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


def register_discovery_endpoints(mcp: FastMCP):
    """Register OAuth2 discovery endpoints as HTTP routes per MCP specification."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    
    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def get_protected_resource_metadata(request: Request) -> JSONResponse:
        """Get OAuth2 Protected Resource Metadata for authorization server discovery"""
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Get discovery service from the global context - this is a simplified approach
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            # Use the server's base URL
            request_url = str(request.base_url).rstrip('/')
            metadata = get_protected_resource_metadata_handler(discovery_service, request_url)
            
            return JSONResponse(
                metadata,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return JSONResponse(
                {"error": str(e)},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def get_authorization_server_metadata(request: Request) -> JSONResponse:
        """Get OAuth2 Authorization Server Metadata - Use our discovery service"""
        
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Get discovery service from global context
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            # Use our discovery service which returns the correct MCP server endpoints
            metadata = discovery_service.get_authorization_server_metadata(request)
            
            # Return our MCP server metadata with correct endpoints
            return JSONResponse(
                metadata,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
        except Exception as e:
            return JSONResponse(
                {"error": f"Failed to fetch authorization server metadata: {str(e)}"},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    @mcp.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def get_openid_configuration(request: Request) -> JSONResponse:
        """Get OpenID Connect discovery metadata - Proxy to Okta"""
        import httpx
        
        try:
            # Handle CORS preflight  
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Get discovery service from global context
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            # Get the provider settings to construct the correct Okta discovery URL
            provider_settings = auth_settings.get_provider_settings()
            if not provider_settings:
                return JSONResponse(
                    {"error": "No authorization servers configured"},
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            
            # Build the correct Okta discovery URL with the authorization server ID
            domain = provider_settings.domain
            if domain.startswith('https://'):
                domain = domain.rstrip('/')
            else:
                domain = f"https://{domain.rstrip('/')}"
            
            auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
            # For OpenID configuration, try the OpenID discovery endpoint first
            okta_openid_url = f"{domain}/oauth2/{auth_server_id}/.well-known/openid_configuration"
            
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(okta_openid_url)
                    response.raise_for_status()
                    metadata = response.json()
                except:
                    # Fallback to OAuth authorization server metadata
                    okta_oauth_url = f"{domain}/oauth2/{auth_server_id}/.well-known/oauth-authorization-server"
                    response = await client.get(okta_oauth_url)
                    response.raise_for_status()
                    metadata = response.json()
                
                # Return the metadata
                return JSONResponse(
                    metadata,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
            
        except Exception as e:
            return JSONResponse(
                {"error": f"Failed to fetch OpenID configuration: {str(e)}"},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    @mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET", "OPTIONS"])
    async def get_mcp_specific_protected_resource(request: Request) -> JSONResponse:
        """Get MCP-specific protected resource metadata"""
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Return the same as the standard protected resource metadata
            # but with MCP-specific information
            auth_settings = AuthenticationSettings(config_file="auth_config.json")
            from .auth import create_discovery_service
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            request_url = str(request.base_url).rstrip('/')
            metadata = get_protected_resource_metadata_handler(discovery_service, request_url)
            
            # Add MCP-specific fields
            metadata["mcp"] = {
                "version": "2025-06-18",
                "capabilities": ["resources", "tools", "prompts"],
                "authentication": {
                    "required": True,
                    "methods": ["oauth2"]
                }
            }
            
            return JSONResponse(
                metadata,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return JSONResponse(
                {"error": str(e)},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    @mcp.custom_route("/oauth/authorize", methods=["GET", "OPTIONS"])
    async def oauth_authorize(request: Request) -> Response:
        """OAuth2 authorization endpoint - redirect to Okta for authentication"""
        from starlette.responses import RedirectResponse
        import secrets
        import hashlib
        import base64
        from urllib.parse import urlencode
        
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Get authorization parameters from query string
            query_params = dict(request.query_params)
            
            # Validate required parameters
            required_params = ['client_id', 'redirect_uri', 'code_challenge', 'response_type']
            for param in required_params:
                if param not in query_params:
                    return JSONResponse(
                        {"error": "invalid_request", "error_description": f"Missing required parameter: {param}"},
                        status_code=400
                    )
            
            # Get provider settings
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            provider_settings = auth_settings.get_provider_settings()
            
            if not provider_settings:
                return JSONResponse(
                    {"error": "server_error", "error_description": "OAuth provider not configured"},
                    status_code=500
                )
            
            # Build Okta authorization URL
            domain = provider_settings.domain.rstrip('/')
            auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
            okta_auth_url = f"{domain}/oauth2/{auth_server_id}/v1/authorize"
            
            # Prepare authorization parameters for Okta
            okta_params = {
                'client_id': provider_settings.client_id,
                'response_type': 'code',
                'scope': ' '.join(provider_settings.scopes or ['openid', 'profile', 'email']),
                'redirect_uri': f"{str(request.base_url).rstrip('/')}/oauth/callback",
                'state': query_params.get('state', secrets.token_urlsafe(32)),
                'code_challenge': query_params['code_challenge'],
                'code_challenge_method': query_params.get('code_challenge_method', 'S256')
            }
            
            # Store original client info for callback (in production, use Redis/database)
            # For now, we'll encode it in the state parameter
            original_client_data = {
                'client_id': query_params['client_id'],
                'redirect_uri': query_params['redirect_uri'],
                'code_challenge': query_params['code_challenge'],
                'state': query_params.get('state')
            }
            
            # Build final authorization URL
            final_url = f"{okta_auth_url}?{urlencode(okta_params)}"
            
            return RedirectResponse(url=final_url, status_code=302)
            
        except Exception as e:
            return JSONResponse(
                {"error": "server_error", "error_description": str(e)},
                status_code=500
            )

    @mcp.custom_route("/oauth/token", methods=["POST", "OPTIONS"])
    async def oauth_token(request: Request) -> JSONResponse:
        """OAuth2 token endpoint - exchange authorization code for access token"""
        import httpx
        
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Parse form data from request
            form_data = await request.form()
            form_dict = dict(form_data)
            
            # Validate required parameters for authorization code grant
            required_params = ['grant_type', 'code', 'redirect_uri', 'client_id', 'code_verifier']
            for param in required_params:
                if param not in form_dict:
                    return JSONResponse(
                        {"error": "invalid_request", "error_description": f"Missing required parameter: {param}"},
                        status_code=400
                    )
            
            if form_dict['grant_type'] != 'authorization_code':
                return JSONResponse(
                    {"error": "unsupported_grant_type", "error_description": "Only authorization_code grant type is supported"},
                    status_code=400
                )
            
            # Get provider settings
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            provider_settings = auth_settings.get_provider_settings()
            
            # Exchange authorization code with Okta
            domain = provider_settings.domain.rstrip('/')
            auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
            token_url = f"{domain}/oauth2/{auth_server_id}/v1/token"
            
            # Prepare token request for Okta
            token_data = {
                'grant_type': 'authorization_code',
                'code': form_dict['code'],
                'redirect_uri': f"{str(request.base_url).rstrip('/')}/oauth/callback",
                'client_id': provider_settings.client_id,
                'code_verifier': form_dict['code_verifier']
            }
            
            # Add client authentication if client_secret is available
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            if hasattr(provider_settings, 'client_secret') and provider_settings.client_secret:
                import base64
                auth_string = base64.b64encode(f"{provider_settings.client_id}:{provider_settings.client_secret}".encode()).decode()
                headers['Authorization'] = f'Basic {auth_string}'
            
            # Exchange code for token with Okta
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=token_data, headers=headers)
                
                if response.status_code != 200:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    return JSONResponse(
                        {
                            "error": error_data.get("error", "invalid_grant"),
                            "error_description": error_data.get("error_description", "Authorization code exchange failed")
                        },
                        status_code=response.status_code
                    )
                
                # Get the token response from Okta
                token_response = response.json()
                
                # Create session for token tracking and logout support
                try:
                    access_token = token_response.get('access_token')
                    refresh_token = token_response.get('refresh_token')
                    expires_in = token_response.get('expires_in')
                    
                    if access_token:
                        # Extract client_id from the original request
                        client_id = form_dict.get('client_id', 'unknown_client')
                        
                        # Create session
                        session_manager.create_session(
                            client_id=client_id,
                            access_token=access_token,
                            refresh_token=refresh_token,
                            expires_in=expires_in,
                            scopes=set(token_response.get('scope', '').split()) if token_response.get('scope') else set()
                        )
                except Exception as e:
                    # Log but don't fail the token response if session creation fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to create session for token: {e}")
                
                return JSONResponse(token_response)
                
        except Exception as e:
            return JSONResponse(
                {"error": "server_error", "error_description": str(e)},
                status_code=500
            )

    @mcp.custom_route("/oauth/callback", methods=["GET"])
    async def oauth_callback(request: Request) -> Response:
        """OAuth2 callback endpoint - handle authorization code from Okta"""
        from starlette.responses import RedirectResponse
        
        try:
            query_params = dict(request.query_params)
            
            # Check for authorization error
            if 'error' in query_params:
                error_description = query_params.get('error_description', 'Authorization failed')
                return JSONResponse(
                    {"error": query_params['error'], "error_description": error_description},
                    status_code=400
                )
            
            # Get authorization code
            if 'code' not in query_params:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "Authorization code not received"},
                    status_code=400
                )
            
            # For Claude integration, we need to redirect back to Claude with the authorization code
            # The actual token exchange will be handled by Claude calling our /oauth/token endpoint
            
            # Extract original client redirect URI from state (simplified approach)
            # In production, this should be stored server-side with proper session management
            original_redirect_uri = "https://claude.ai/api/mcp/auth_callback"  # Claude's callback
            
            # Redirect back to original client (Claude) with authorization code
            callback_params = {
                'code': query_params['code'],
                'state': query_params.get('state', '')
            }
            
            callback_url = f"{original_redirect_uri}?{urlencode(callback_params)}"
            return RedirectResponse(url=callback_url, status_code=302)
            
        except Exception as e:
            return JSONResponse(
                {"error": "server_error", "error_description": str(e)},
                status_code=500
            )

    @mcp.custom_route("/oauth/revoke", methods=["POST", "OPTIONS"])
    async def oauth_revoke_token(request: Request) -> JSONResponse:
        """OAuth2 token revocation endpoint (RFC 7009)"""
        import httpx
        
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Parse form data
            form_data = await request.form()
            form_dict = dict(form_data)
            
            # Validate required parameters
            if 'token' not in form_dict:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "Missing required parameter: token"},
                    status_code=400
                )
            
            token = form_dict['token']
            token_type_hint = form_dict.get('token_type_hint', 'access_token')
            
            # Revoke token in our session manager
            session_manager.revoke_token(token)
            
            # Also revoke with Okta
            try:
                from .auth.settings import load_auth_config_from_file
                config_data = load_auth_config_from_file("auth_config.json")
                auth_settings = AuthenticationSettings(**config_data)
                provider_settings = auth_settings.get_provider_settings()
                
                if provider_settings:
                    domain = provider_settings.domain.rstrip('/')
                    auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
                    revoke_url = f"{domain}/oauth2/{auth_server_id}/v1/revoke"
                    
                    # Prepare revocation request
                    revoke_data = {
                        'token': token,
                        'token_type_hint': token_type_hint
                    }
                    
                    # Add client authentication
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                    if hasattr(provider_settings, 'client_secret') and provider_settings.client_secret:
                        import base64
                        auth_string = base64.b64encode(f"{provider_settings.client_id}:{provider_settings.client_secret}".encode()).decode()
                        headers['Authorization'] = f'Basic {auth_string}'
                    else:
                        revoke_data['client_id'] = provider_settings.client_id
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(revoke_url, data=revoke_data, headers=headers)
                        # Note: RFC 7009 states that revocation endpoint should return 200 even for invalid tokens
                        
            except Exception as e:
                # Log but don't fail the revocation if Okta call fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to revoke token with Okta: {e}")
            
            # Always return success for revocation per RFC 7009
            return JSONResponse(
                {},
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
        except Exception as e:
            return JSONResponse(
                {"error": "server_error", "error_description": str(e)},
                status_code=500
            )

    @mcp.custom_route("/oauth/logout", methods=["POST", "GET", "OPTIONS"])
    async def oauth_logout(request: Request) -> JSONResponse:
        """Logout endpoint for Claude Desktop disconnection"""
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Extract token from Authorization header or request body
            token = None
            
            # Try Authorization header first
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            
            # Try request body for POST
            if not token and request.method == "POST":
                try:
                    if request.headers.get('content-type', '').startswith('application/x-www-form-urlencoded'):
                        form_data = await request.form()
                        token = form_data.get('token')
                    elif request.headers.get('content-type', '').startswith('application/json'):
                        json_data = await request.json()
                        token = json_data.get('token')
                except:
                    pass
            
            # Try query parameter for GET
            if not token and request.method == "GET":
                token = request.query_params.get('token')
            
            if not token:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "No token provided for logout"},
                    status_code=400
                )
            
            # Find and remove session
            session = session_manager.get_session_by_token(token)
            if session:
                # Remove session and revoke all tokens
                session_manager.remove_session(session.client_id)
                
                # Optionally revoke tokens with Okta
                try:
                    from .auth.settings import load_auth_config_from_file
                    config_data = load_auth_config_from_file("auth_config.json")
                    auth_settings = AuthenticationSettings(**config_data)
                    provider_settings = auth_settings.get_provider_settings()
                    
                    if provider_settings and hasattr(provider_settings, 'client_secret') and provider_settings.client_secret:
                        domain = provider_settings.domain.rstrip('/')
                        auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
                        revoke_url = f"{domain}/oauth2/{auth_server_id}/v1/revoke"
                        
                        import httpx
                        import base64
                        
                        # Revoke access token
                        auth_string = base64.b64encode(f"{provider_settings.client_id}:{provider_settings.client_secret}".encode()).decode()
                        headers = {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'Authorization': f'Basic {auth_string}'
                        }
                        
                        async with httpx.AsyncClient() as client:
                            # Revoke access token
                            await client.post(revoke_url, data={'token': session.access_token, 'token_type_hint': 'access_token'}, headers=headers)
                            
                            # Revoke refresh token if available
                            if session.refresh_token:
                                await client.post(revoke_url, data={'token': session.refresh_token, 'token_type_hint': 'refresh_token'}, headers=headers)
                                
                except Exception as e:
                    # Log but don't fail logout if Okta revocation fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to revoke tokens with Okta during logout: {e}")
                
                return JSONResponse(
                    {"message": "Logout successful", "revoked_tokens": ["access_token", "refresh_token"] if session.refresh_token else ["access_token"]},
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            else:
                # Token not found in our sessions, but still return success
                return JSONResponse(
                    {"message": "Logout successful", "note": "No active session found"},
                    headers={"Access-Control-Allow-Origin": "*"}
                )
                
        except Exception as e:
            return JSONResponse(
                {"error": "server_error", "error_description": str(e)},
                status_code=500
            )

    @mcp.custom_route("/register", methods=["POST", "OPTIONS"])
    async def register_oauth2_client(request: Request) -> JSONResponse:
        """Register a new OAuth2 client dynamically (RFC 7591)"""
        try:
            # Handle CORS preflight
            if request.method == "OPTIONS":
                return JSONResponse({}, headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                })
            
            # Get discovery service from global context
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            # Parse request body
            registration_data = await request.json()
            
            response = register_client_handler(discovery_service, registration_data)
            
            return JSONResponse(
                response,
                status_code=201,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return JSONResponse(
                {"error": str(e)},
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    


def register_client_tool(mcp: FastMCP):
    """Register OAuth2 client registration tool"""
    
    # Register a helper tool for OAuth2 client registration (MCP tool version)
    @mcp.tool(description="Register OAuth2 client dynamically via MCP (RFC 7591)")
    def register_oauth2_client_tool(
        redirect_uris: List[str],
        client_name: Optional[str] = None,
        client_uri: Optional[str] = None,
        logo_uri: Optional[str] = None,
        scope: Optional[str] = None,
        contacts: Optional[List[str]] = None,
        tos_uri: Optional[str] = None,
        policy_uri: Optional[str] = None,
        software_id: Optional[str] = None,
        software_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new OAuth2 client dynamically via MCP protocol
        
        This tool allows MCP clients to register themselves with the OAuth2 
        authorization server to obtain client credentials.
        """
        try:
            # Get discovery service from the global context - simplified approach
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, "http://localhost:8000")
            
            registration_data = {
                "redirect_uris": redirect_uris,
                "client_name": client_name,
                "client_uri": client_uri,
                "logo_uri": logo_uri,
                "scope": scope,
                "contacts": contacts,
                "tos_uri": tos_uri,
                "policy_uri": policy_uri,
                "software_id": software_id,
                "software_version": software_version
            }
            
            # Remove None values
            registration_data = {k: v for k, v in registration_data.items() if v is not None}
            
            response = register_client_handler(discovery_service, registration_data)
            return {"success": True, "client_registration": response}
        except Exception as e:
            return {"success": False, "error": str(e)}


def setup_http_discovery_routes(mcp: FastMCP):
    """Setup HTTP routes for OAuth2 discovery endpoints on the Starlette app"""
    try:
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError:
        # Fallback - skip HTTP route setup if dependencies not available
        return
    
    # Get the Starlette app from FastMCP
    app = mcp.streamable_http_app()
    
    async def http_protected_resource_metadata(request: Request):
        """HTTP endpoint for protected resource metadata"""
        try:
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            request_url = str(request.base_url).rstrip('/')
            metadata = get_protected_resource_metadata_handler(discovery_service, request_url)
            
            return JSONResponse(
                metadata,
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception as e:
            return JSONResponse(
                {"error": str(e)},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    async def http_authorization_server_metadata(request: Request):
        """HTTP endpoint for authorization server metadata - Proxy to Okta"""
        import httpx
        
        try:
            from .auth.settings import load_auth_config_from_file
            config_data = load_auth_config_from_file("auth_config.json")
            auth_settings = AuthenticationSettings(**config_data)
            discovery_service = create_discovery_service(auth_settings, str(request.base_url).rstrip('/'))
            
            # Get the provider settings to construct the correct Okta discovery URL
            provider_settings = auth_settings.get_provider_settings()
            if not provider_settings:
                return JSONResponse(
                    {"error": "No authorization servers configured"},
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            
            # Build the correct Okta discovery URL with the authorization server ID
            domain = provider_settings.domain
            if domain.startswith('https://'):
                domain = domain.rstrip('/')
            else:
                domain = f"https://{domain.rstrip('/')}"
            
            auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
            okta_discovery_url = f"{domain}/oauth2/{auth_server_id}/.well-known/oauth-authorization-server"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(okta_discovery_url)
                response.raise_for_status()
                
                metadata = response.json()
                
                # Return the Okta metadata
                return JSONResponse(
                    metadata,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
        except Exception as e:
            return JSONResponse(
                {"error": f"Failed to fetch authorization server metadata: {str(e)}"},
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"}
            )
    
    # Add routes to the Starlette app
    discovery_routes = [
        Route("/.well-known/oauth-protected-resource", http_protected_resource_metadata, methods=["GET"]),
        Route("/.well-known/oauth-authorization-server", http_authorization_server_metadata, methods=["GET"]),
    ]
    
    # Extend the app's router with discovery routes
    app.router.routes.extend(discovery_routes)
