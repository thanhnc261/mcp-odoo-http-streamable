"""
OAuth2 authentication system for MCP server with Okta provider.
"""

from .factory import create_token_verifier
from .settings import (
    AuthenticationSettings,
    OktaSettings,
    ProviderType
)
from .discovery import (
    OAuth2DiscoveryService,
    ProtectedResourceMetadata,
    AuthorizationServerMetadata,
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    create_discovery_service,
    get_protected_resource_metadata_handler,
    get_authorization_server_metadata_handler,
    register_client_handler
)

__all__ = [
    "create_token_verifier",
    "AuthenticationSettings", 
    "OktaSettings",
    "ProviderType",
    "OAuth2DiscoveryService",
    "ProtectedResourceMetadata",
    "AuthorizationServerMetadata", 
    "ClientRegistrationRequest",
    "ClientRegistrationResponse",
    "create_discovery_service",
    "get_protected_resource_metadata_handler",
    "get_authorization_server_metadata_handler",
    "register_client_handler",
]
