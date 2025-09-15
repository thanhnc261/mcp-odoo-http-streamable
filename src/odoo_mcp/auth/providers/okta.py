"""
Okta OAuth2 provider implementation for MCP authentication.
"""

import logging
import time
from typing import Any, Dict, Optional
import httpx
import jwt
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from mcp.server.auth.provider import AccessToken
from .base import BaseOAuth2Provider, DiscoveryDocument
from ..settings import OktaSettings

logger = logging.getLogger(__name__)


class OktaOAuth2Provider(BaseOAuth2Provider):
    """Okta OAuth2/OIDC provider implementation."""
    
    def __init__(self, settings: OktaSettings):
        if not settings.domain:
            raise ValueError("Okta domain is required")
        if not settings.client_id:
            raise ValueError("Okta client ID is required")
        
        super().__init__(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            redirect_uri=settings.redirect_uri[0] if settings.redirect_uri else None,
            scopes=settings.scopes,
        )
        
        self.settings = settings
        self.domain = settings.domain.rstrip('/')
        if not self.domain.startswith('https://'):
            self.domain = f"https://{self.domain}"
        
        self.authorization_server_id = settings.authorization_server_id or "default"
        
        # Okta endpoints
        self.issuer_url = f"{self.domain}/oauth2/{self.authorization_server_id}"
        self.well_known_url = f"{self.issuer_url}/.well-known/oauth_authorization_server"
        
        # Cache for JWKS and discovery
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time = 0
        self.jwks_cache_ttl = getattr(settings, 'jwks_cache_ttl', 3600)
    
    async def discover_endpoints(self) -> Optional[DiscoveryDocument]:
        """Discover Okta OAuth2/OIDC endpoints."""
        if self._discovery_document:
            return self._discovery_document
        
        # Try multiple discovery URLs as Okta can be inconsistent
        discovery_urls = [
            f"{self.issuer_url}/.well-known/oauth_authorization_server",
            f"{self.issuer_url}/.well-known/openid_configuration"
        ]
        
        for url in discovery_urls:
            try:
                client = await self._get_http_client()
                
                # Try with different headers to work around Okta quirks
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "MCP-Server/1.0"
                }
                
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                config = response.json()
                
                self._discovery_document = DiscoveryDocument(
                    issuer=config["issuer"],
                    authorization_endpoint=config["authorization_endpoint"],
                    token_endpoint=config["token_endpoint"],
                    jwks_uri=config["jwks_uri"],
                    userinfo_endpoint=config.get("userinfo_endpoint"),
                    introspection_endpoint=config.get("introspection_endpoint"),
                    revocation_endpoint=config.get("revocation_endpoint"),
                    scopes_supported=config.get("scopes_supported"),
                    response_types_supported=config.get("response_types_supported"),
                    grant_types_supported=config.get("grant_types_supported"),
                    token_endpoint_auth_methods_supported=config.get("token_endpoint_auth_methods_supported"),
                )
                
                logger.info(f"Successfully discovered Okta endpoints from {url}")
                return self._discovery_document
                
            except Exception as e:
                logger.warning(f"Failed to discover from {url}: {e}")
                continue
        
        # If discovery fails, create a fallback configuration based on known Okta patterns
        logger.warning("All discovery attempts failed, using fallback configuration")
        try:
            self._discovery_document = DiscoveryDocument(
                issuer=self.issuer_url,
                authorization_endpoint=f"{self.issuer_url}/v1/authorize",
                token_endpoint=f"{self.issuer_url}/v1/token",
                jwks_uri=f"{self.issuer_url}/v1/keys",
                introspection_endpoint=f"{self.issuer_url}/v1/introspect",
                revocation_endpoint=f"{self.issuer_url}/v1/revoke",
                scopes_supported=["openid", "profile", "email", "offline_access"],
                response_types_supported=["code", "token", "id_token"],
                grant_types_supported=["authorization_code", "refresh_token", "implicit"],
                token_endpoint_auth_methods_supported=["client_secret_basic", "client_secret_post", "none"],
            )
            
            logger.info("Using fallback Okta endpoint configuration")
            return self._discovery_document
            
        except Exception as e:
            logger.exception("Failed to create fallback configuration")
            return None
    
    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load and validate Okta access token."""
        try:
            # Try JWT validation first
            if self._is_jwt_token(token):
                payload = await self._validate_jwt_token(token)
                if payload:
                    return AccessToken(
                        token=token,
                        client_id=payload.get("cid", ""),
                        scopes=payload.get("scp", []),
                        expires_at=payload.get("exp"),
                        resource=self.settings.audience
                    )
            
            # Fallback to introspection
            if self._discovery_document and self._discovery_document.introspection_endpoint:
                return await self._introspect_token(token)
            
            return None
            
        except Exception as e:
            logger.exception(f"Failed to validate token")
            return None
    
    def _is_jwt_token(self, token: str) -> bool:
        """Check if token is a JWT."""
        return len(token.split('.')) == 3
    
    async def _validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token using Okta's JWKS."""
        try:
            # Get JWKS
            jwks = await self._get_jwks()
            if not jwks:
                return None
            
            # Decode JWT header to get key ID
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            # Find matching key
            key = None
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    key = RSAAlgorithm.from_jwk(jwk)
                    break
            
            if not key:
                logger.warning(f"No matching key found for kid: {kid}")
                return None
            
            # Validate token
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                audience=self.settings.audience if self.settings.validate_audience else None,
                options={
                    "verify_iss": self.settings.validate_issuer,
                    "verify_aud": self.settings.validate_audience,
                }
            )
            
            return payload
            
        except InvalidTokenError as e:
            logger.warning(f"JWT validation failed: {e}")
            return None
        except Exception as e:
            logger.exception("Error validating JWT token")
            return None
    
    async def _get_jwks(self) -> Optional[Dict[str, Any]]:
        """Get JWKS from Okta, with caching."""
        current_time = time.time()
        
        # Check cache
        if (self._jwks_cache and 
            current_time - self._jwks_cache_time < self.jwks_cache_ttl):
            return self._jwks_cache
        
        try:
            discovery = await self.discover_endpoints()
            if not discovery or not discovery.jwks_uri:
                return None
            
            client = await self._get_http_client()
            response = await client.get(discovery.jwks_uri)
            response.raise_for_status()
            
            self._jwks_cache = response.json()
            self._jwks_cache_time = current_time
            
            return self._jwks_cache
            
        except Exception as e:
            logger.exception("Failed to fetch JWKS")
            return None
    
    async def _introspect_token(self, token: str) -> Optional[AccessToken]:
        """Introspect token using Okta's introspection endpoint."""
        try:
            discovery = await self.discover_endpoints()
            if not discovery or not discovery.introspection_endpoint:
                return None
            
            client = await self._get_http_client()
            
            # Prepare introspection request
            data = {"token": token}
            auth = None
            if self.client_secret:
                auth = (self.client_id, self.client_secret)
            else:
                data["client_id"] = self.client_id
            
            response = await client.post(
                discovery.introspection_endpoint,
                data=data,
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("active"):
                return None
            
            return AccessToken(
                token=token,
                client_id=result.get("client_id", ""),
                scopes=result.get("scope", "").split() if result.get("scope") else [],
                expires_at=result.get("exp"),
                resource=self.settings.audience
            )
            
        except Exception as e:
            logger.exception("Token introspection failed")
            return None