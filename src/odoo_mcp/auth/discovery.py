"""
OAuth2 discovery and metadata endpoints for MCP server.

Implements RFC 8414 (Authorization Server Metadata), RFC 9728 (Protected Resource Metadata),
and RFC 7591 (Dynamic Client Registration) as required by the MCP OAuth2 specification.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

try:
    from fastapi import HTTPException, Request, Response
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Define placeholder classes for type hints
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    
    class Request:
        pass
    
    class JSONResponse:
        pass

from pydantic import BaseModel, AnyHttpUrl

from .settings import AuthenticationSettings, ProviderType

logger = logging.getLogger(__name__)


class ProtectedResourceMetadata(BaseModel):
    """Protected Resource Metadata as per RFC 9728."""
    
    resource: AnyHttpUrl
    authorization_servers: List[AnyHttpUrl]
    scopes_supported: Optional[List[str]] = None
    bearer_methods_supported: Optional[List[str]] = ["header"]
    resource_documentation: Optional[AnyHttpUrl] = None


class AuthorizationServerMetadata(BaseModel):
    """Authorization Server Metadata as per RFC 8414."""
    
    issuer: AnyHttpUrl
    authorization_endpoint: AnyHttpUrl
    token_endpoint: AnyHttpUrl
    jwks_uri: Optional[AnyHttpUrl] = None
    registration_endpoint: Optional[AnyHttpUrl] = None
    scopes_supported: Optional[List[str]] = None
    response_types_supported: List[str] = ["code"]
    grant_types_supported: List[str] = ["authorization_code", "refresh_token"]
    token_endpoint_auth_methods_supported: List[str] = ["client_secret_basic", "client_secret_post", "none"]
    code_challenge_methods_supported: List[str] = ["S256"]
    resource_servers: Optional[List[AnyHttpUrl]] = None


class ClientRegistrationRequest(BaseModel):
    """Dynamic Client Registration Request as per RFC 7591."""
    
    redirect_uris: List[AnyHttpUrl]
    client_name: Optional[str] = None
    client_uri: Optional[AnyHttpUrl] = None
    logo_uri: Optional[AnyHttpUrl] = None
    scope: Optional[str] = None
    contacts: Optional[List[str]] = None
    tos_uri: Optional[AnyHttpUrl] = None
    policy_uri: Optional[AnyHttpUrl] = None
    software_id: Optional[str] = None
    software_version: Optional[str] = None


class ClientRegistrationResponse(BaseModel):
    """Dynamic Client Registration Response as per RFC 7591."""
    
    client_id: str
    client_secret: Optional[str] = None
    client_id_issued_at: Optional[int] = None
    client_secret_expires_at: Optional[int] = None
    redirect_uris: List[str]
    client_name: Optional[str] = None
    client_uri: Optional[str] = None
    logo_uri: Optional[str] = None
    scope: Optional[str] = None
    contacts: Optional[List[str]] = None
    tos_uri: Optional[str] = None
    policy_uri: Optional[str] = None
    software_id: Optional[str] = None
    software_version: Optional[str] = None


class OAuth2DiscoveryService:
    """OAuth2 discovery and metadata service for MCP server."""
    
    def __init__(self, settings: AuthenticationSettings, base_url: str = "http://localhost:8000"):
        self.settings = settings
        self.base_url = base_url.rstrip('/')
        self.resource_server_url = base_url
        
        # Simple in-memory client registry for demo purposes
        # In production, this should be persistent storage
        self.registered_clients: Dict[str, Dict[str, Any]] = {}
    
    def get_base_url_from_request(self, request: Request) -> str:
        """Extract base URL from request."""
        scheme = request.url.scheme
        host = request.headers.get("host", request.url.netloc)
        return f"{scheme}://{host}"
    
    def get_protected_resource_metadata(self, request: Request) -> Dict[str, Any]:
        """
        Generate Protected Resource Metadata as per RFC 9728.
        
        This is the primary discovery endpoint that clients use to find
        the authorization server(s) for this MCP server.
        """
        base_url = self.get_base_url_from_request(request)
        
        # Get authorization server URLs based on provider
        authorization_servers = self._get_authorization_server_urls(base_url)
        
        metadata = ProtectedResourceMetadata(
            resource=base_url,
            authorization_servers=authorization_servers,
            scopes_supported=self._get_supported_scopes(),
            bearer_methods_supported=["header"],
            resource_documentation=f"{base_url}/docs"
        )
        
        # Convert to dict and serialize URLs as strings
        result = metadata.model_dump(exclude_none=True)
        
        # Convert AnyHttpUrl objects to strings for JSON serialization
        if 'resource' in result:
            result['resource'] = str(result['resource'])
        if 'authorization_servers' in result:
            result['authorization_servers'] = [str(url) for url in result['authorization_servers']]
        if 'resource_documentation' in result:
            result['resource_documentation'] = str(result['resource_documentation'])
            
        return result
    
    def get_authorization_server_metadata(self, request: Request) -> Dict[str, Any]:
        """
        Generate Authorization Server Metadata as per RFC 8414.
        
        This endpoint provides information about the authorization server
        capabilities and endpoints.
        """
        base_url = self.get_base_url_from_request(request)
        
        if not self.settings.is_enabled():
            raise HTTPException(status_code=404, detail="OAuth2 not enabled")
        
        provider_settings = self.settings.get_provider_settings()
        if not provider_settings:
            raise HTTPException(status_code=500, detail="Provider settings not found")
        
        # Generate metadata based on provider type
        if self.settings.provider == ProviderType.OKTA:
            return self._get_okta_authorization_server_metadata(base_url, provider_settings)
        else:
            raise HTTPException(status_code=500, detail=f"Unsupported provider: {self.settings.provider}")
    
    def _get_okta_authorization_server_metadata(self, base_url: str, provider_settings) -> Dict[str, Any]:
        """Generate Okta authorization server metadata by proxying to actual Okta discovery."""
        # Extract domain from the Okta settings
        domain = provider_settings.domain
        # Handle domain with or without https:// prefix and trailing slash
        if domain.startswith('https://'):
            domain = domain.rstrip('/')
        else:
            domain = f"https://{domain.rstrip('/')}"
        
        # Determine authorization server ID
        auth_server_id = getattr(provider_settings, 'authorization_server_id', 'default')
        
        # Build MCP server endpoints that proxy to Okta
        # Claude Desktop will call our server's OAuth endpoints, which will handle the Okta integration
        issuer = f"{domain}/oauth2/{auth_server_id}"  # Keep Okta issuer for token validation
        authorization_endpoint = f"{base_url}/oauth/authorize"  # Our MCP server's auth endpoint
        token_endpoint = f"{base_url}/oauth/token"  # Our MCP server's token endpoint
        jwks_uri = f"{domain}/oauth2/{auth_server_id}/v1/keys"  # Okta's JWKS for token validation
        registration_endpoint = f"{base_url}/register"  # Our MCP server's DCR endpoint
        introspection_endpoint = f"{domain}/oauth2/{auth_server_id}/v1/introspect"  # Okta's introspection
        revocation_endpoint = f"{base_url}/oauth/revoke"  # Our MCP server's revocation endpoint
        
        # Return the actual Okta authorization server metadata
        metadata = AuthorizationServerMetadata(
            issuer=issuer,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            jwks_uri=jwks_uri,
            registration_endpoint=registration_endpoint,
            scopes_supported=self._get_supported_scopes(),
            response_types_supported=["code", "token", "id_token", "code id_token", "code token", "id_token token", "code id_token token"],
            grant_types_supported=["authorization_code", "refresh_token", "implicit"],
            token_endpoint_auth_methods_supported=[
                "none" if not hasattr(provider_settings, 'client_secret') or not provider_settings.client_secret else "client_secret_basic"
            ],
            code_challenge_methods_supported=["S256"],
            resource_servers=[base_url]
        )
        
        # Add additional Okta-specific fields
        metadata_dict = metadata.model_dump(exclude_none=True)
        metadata_dict.update({
            "introspection_endpoint": introspection_endpoint,
            "introspection_endpoint_auth_methods_supported": [
                "client_secret_basic"
            ],
            "revocation_endpoint": revocation_endpoint,
            "revocation_endpoint_auth_methods_supported": [
                "client_secret_basic"
            ],
            "subject_types_supported": ["public"],
            "response_modes_supported": ["query", "fragment", "form_post"],
            "claims_supported": ["ver", "jti", "iss", "aud", "iat", "exp", "cid", "uid", "scp", "sub"],
            "token_endpoint_auth_method": "none" if not hasattr(provider_settings, 'client_secret') or not provider_settings.client_secret else "client_secret_basic"
        })
        
        # Convert AnyHttpUrl objects to strings for JSON serialization
        for key in ['issuer', 'authorization_endpoint', 'token_endpoint', 'jwks_uri', 'registration_endpoint', 
                    'introspection_endpoint', 'revocation_endpoint']:
            if key in metadata_dict and metadata_dict[key]:
                metadata_dict[key] = str(metadata_dict[key])
        
        if 'resource_servers' in metadata_dict:
            metadata_dict['resource_servers'] = [str(url) for url in metadata_dict['resource_servers']]
        
        return metadata_dict
    
    def register_client(self, request: ClientRegistrationRequest) -> ClientRegistrationResponse:
        """
        Handle dynamic client registration as per RFC 7591.
        
        Generates a new client ID and optionally a client secret
        for the requesting client.
        """
        if not self.settings.is_enabled():
            raise HTTPException(status_code=404, detail="OAuth2 not enabled")
        
        # Generate client credentials
        client_id = f"mcp_client_{uuid.uuid4().hex[:16]}"
        client_secret = f"mcp_secret_{uuid.uuid4().hex}"
        
        # Set expiration times
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = int((datetime.utcnow() + timedelta(days=365)).timestamp())
        
        # Store client registration (in production, use persistent storage)
        client_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": issued_at,
            "client_secret_expires_at": expires_at,
            "redirect_uris": [str(uri) for uri in request.redirect_uris],
            "client_name": request.client_name,
            "client_uri": str(request.client_uri) if request.client_uri else None,
            "logo_uri": str(request.logo_uri) if request.logo_uri else None,
            "scope": request.scope or " ".join(self._get_supported_scopes()),
            "contacts": request.contacts,
            "tos_uri": str(request.tos_uri) if request.tos_uri else None,
            "policy_uri": str(request.policy_uri) if request.policy_uri else None,
            "software_id": request.software_id,
            "software_version": request.software_version,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.registered_clients[client_id] = client_data
        
        logger.info(f"Registered new OAuth2 client: {client_id} ({request.client_name})")
        
        return ClientRegistrationResponse(**client_data)
    
    def create_www_authenticate_header(self, resource_url: Optional[str] = None) -> str:
        """
        Create WWW-Authenticate header as per RFC 9728 Section 5.1.
        
        This header is returned in 401 responses to indicate where
        clients can find the protected resource metadata.
        """
        if not resource_url:
            resource_url = self.resource_server_url
        
        metadata_url = f"{resource_url}/.well-known/oauth-protected-resource"
        
        return f'Bearer realm="MCP Server", resource_metadata="{metadata_url}"'
    
    def _get_authorization_server_urls(self, base_url: str = None) -> List[str]:
        """Get list of authorization server URLs based on configuration."""
        if not self.settings.is_enabled():
            return []
        
        provider_settings = self.settings.get_provider_settings()
        if not provider_settings:
            return []
        
        if self.settings.provider == ProviderType.OKTA:
            domain = provider_settings.domain
            # Handle domain with or without https:// prefix and trailing slash
            if domain.startswith('https://'):
                domain = domain.rstrip('/')
            else:
                domain = f"https://{domain.rstrip('/')}"
            
            # Return the MCP server's base URL as the authorization server
            # The Inspector will append /.well-known/oauth-authorization-server to this
            # and call our proxy endpoint which will return the correct Okta metadata
            
            # This ensures Inspector calls: http://localhost:8000/.well-known/oauth-authorization-server
            # instead of: https://trial-2386786.okta.com/.well-known/oauth-authorization-server
            # Our proxy will then return the correct Okta authorization server metadata
            
            # Use the provided base_url or fall back to the configured one
            actual_base_url = base_url or self.base_url
            return [actual_base_url]
        
        return []
    
    def _get_supported_scopes(self) -> List[str]:
        """Get list of supported OAuth2 scopes."""
        provider_settings = self.settings.get_provider_settings()
        
        if provider_settings and hasattr(provider_settings, 'scopes'):
            return provider_settings.scopes
        
        # Default scopes
        return ["openid", "profile", "email", "odoo:read", "odoo:write", "hr:read"]


def create_discovery_service(
    settings: Optional[AuthenticationSettings] = None,
    base_url: str = "http://localhost:8000"
) -> OAuth2DiscoveryService:
    """
    Create OAuth2 discovery service with optional settings.
    
    Args:
        settings: Authentication settings (will create default if None)
        base_url: Base URL of the MCP server
        
    Returns:
        OAuth2DiscoveryService instance
    """
    if settings is None:
        settings = AuthenticationSettings()
    
    return OAuth2DiscoveryService(settings, base_url)


# Generic discovery handlers (can be adapted to any web framework)
def get_protected_resource_metadata_handler(discovery_service: OAuth2DiscoveryService, request_url: str) -> Dict[str, Any]:
    """Protected Resource Metadata handler (RFC 9728)."""
    try:
        # Create a minimal request object with URL info
        class MockRequest:
            def __init__(self, url: str):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                self.url = type('URL', (), {
                    'scheme': parsed.scheme,
                    'netloc': parsed.netloc
                })()
                self.headers = {"host": parsed.netloc}
        
        request = MockRequest(request_url)
        return discovery_service.get_protected_resource_metadata(request)
    except Exception as e:
        logger.error(f"Error generating protected resource metadata: {e}")
        raise

def get_authorization_server_metadata_handler(discovery_service: OAuth2DiscoveryService, request_url: str) -> Dict[str, Any]:
    """Authorization Server Metadata handler (RFC 8414)."""
    try:
        class MockRequest:
            def __init__(self, url: str):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                self.url = type('URL', (), {
                    'scheme': parsed.scheme,
                    'netloc': parsed.netloc
                })()
                self.headers = {"host": parsed.netloc}
        
        request = MockRequest(request_url)
        return discovery_service.get_authorization_server_metadata(request)
    except Exception as e:
        logger.error(f"Error generating authorization server metadata: {e}")
        raise

def register_client_handler(discovery_service: OAuth2DiscoveryService, registration_data: Dict[str, Any]) -> Dict[str, Any]:
    """Dynamic Client Registration handler (RFC 7591)."""
    try:
        request = ClientRegistrationRequest(**registration_data)
        response = discovery_service.register_client(request)
        return response.model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        raise
