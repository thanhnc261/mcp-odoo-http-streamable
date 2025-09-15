"""
Factory for creating OAuth2 token verifiers.
"""

import logging
from typing import Optional

from mcp.server.auth.provider import TokenVerifier
from .providers.base import TokenVerifierProvider
from .providers.okta import OktaOAuth2Provider
from .settings import AuthenticationSettings, ProviderType

logger = logging.getLogger(__name__)


def create_token_verifier(settings: AuthenticationSettings) -> Optional[TokenVerifier]:
    """
    Create MCP-compatible token verifier based on settings.
    
    Args:
        settings: Authentication settings with provider configuration
        
    Returns:
        TokenVerifier instance or None if disabled/invalid
    """
    if not settings.is_enabled():
        logger.info("OAuth2 authentication is disabled")
        return None
    
    provider_settings = settings.get_provider_settings()
    if not provider_settings:
        logger.error(f"No settings found for provider: {settings.provider}")
        return None
    
    try:
        if settings.provider == ProviderType.OKTA:
            logger.info("Creating Okta OAuth2 token verifier")
            provider = OktaOAuth2Provider(settings.okta)
            return TokenVerifierProvider(provider)
        
        else:
            logger.error(f"Unsupported OAuth2 provider: {settings.provider}")
            return None
            
    except Exception as e:
        logger.exception(f"Failed to create OAuth2 provider {settings.provider}")
        return None
