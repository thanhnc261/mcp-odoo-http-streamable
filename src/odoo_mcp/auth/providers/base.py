"""
OAuth2 provider implementations for MCP authentication.
"""

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
import httpx
from mcp.server.auth.provider import (
    AccessToken, 
    AuthorizationCode,
    RefreshToken,
    OAuthAuthorizationServerProvider,
    TokenVerifier
)
from mcp.shared.auth import OAuthClientInformationFull

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryDocument:
    """OAuth2/OIDC discovery document."""
    
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    introspection_endpoint: Optional[str] = None
    revocation_endpoint: Optional[str] = None
    scopes_supported: Optional[list[str]] = None
    response_types_supported: Optional[list[str]] = None
    grant_types_supported: Optional[list[str]] = None
    token_endpoint_auth_methods_supported: Optional[list[str]] = None
    extra_fields: Optional[Dict[str, Any]] = None


class TokenVerifierProvider(TokenVerifier):
    """Base token verifier using OAuth2 introspection or JWT validation."""
    
    def __init__(self, provider: "BaseOAuth2Provider"):
        self.provider = provider
    
    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token using the provider's token validation."""
        return await self.provider.load_access_token(token)


class BaseOAuth2Provider:
    """Base OAuth2 provider with common functionality."""
    
    def __init__(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["openid", "profile", "email"]
        
        self._discovery_document: Optional[DiscoveryDocument] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def discover_endpoints(self) -> Optional[DiscoveryDocument]:
        """Discover OAuth2/OIDC endpoints from well-known configuration."""
        raise NotImplementedError("Subclasses must implement discover_endpoints")
    
    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load and validate access token."""
        raise NotImplementedError("Subclasses must implement load_access_token")
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None