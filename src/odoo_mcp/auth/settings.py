"""
OAuth2 authentication settings for MCP server with Okta provider.

Configurable via environment variables with MCP_AUTH_ prefix or auth_config.json file.
Provides OAuth2 authentication using Okta as the identity provider.
"""

import json
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderType(str, Enum):
    """Supported OAuth2 providers."""
    
    DISABLED = "disabled"
    OKTA = "okta"



def load_auth_config_from_file(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load authentication configuration from JSON file.
    
    Args:
        config_path: Path to configuration file. Defaults to auth_config.json in current directory.
        
    Returns:
        Dictionary containing configuration data, empty dict if file not found.
    """
    if config_path is None:
        config_path = "auth_config.json"
    
    config_file = Path(config_path)
    
    # Also try relative to the current working directory
    if not config_file.exists():
        cwd_config = Path.cwd() / config_path
        if cwd_config.exists():
            config_file = cwd_config
    
    # Try relative to this module's directory
    if not config_file.exists():
        module_dir = Path(__file__).parent.parent.parent.parent  # Go up to project root
        module_config = module_dir / config_path
        if module_config.exists():
            config_file = module_config
    
    if not config_file.exists():
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load auth config from {config_file}: {e}")
        return {}


class BaseOAuth2Settings(BaseSettings):
    """Base OAuth2 provider settings with common fields."""
    
    enabled: bool = Field(True, description="Enable OAuth2 authentication")
    client_id: Optional[str] = Field(None, description="OAuth2 client ID")
    client_secret: Optional[str] = Field(None, description="OAuth2 client secret")
    redirect_uri: Optional[Union[str, list[str]]] = Field(None, description="OAuth2 redirect URI(s)")
    scopes: list[str] = Field(["openid", "profile", "email"], description="OAuth2 scopes")
    
    # Token validation settings
    validate_audience: bool = Field(True, description="Validate token audience")
    validate_issuer: bool = Field(True, description="Validate token issuer")
    token_cache_ttl: int = Field(300, description="Token cache TTL in seconds")
    
    @classmethod
    def from_config_dict(cls, config: Dict[str, Any]):
        """Create settings instance from configuration dictionary."""
        return cls(**config)
    

class OktaSettings(BaseOAuth2Settings):
    """Okta OAuth2 provider settings."""
    
    # Okta-specific settings
    domain: Optional[str] = Field(None, description="Okta domain (e.g., dev-12345.okta.com)")
    authorization_server_id: str = Field("default", description="Okta authorization server ID")
    audience: Optional[str] = Field(None, description="Token audience (defaults to client_id)")
    
    # Okta-specific validation settings
    jwks_cache_ttl: int = Field(3600, description="JWKS cache TTL in seconds")
    validation_method: str = Field("hybrid", description="Token validation method (jwt, introspection, hybrid)")
    audience: Optional[str] = Field(None, description="Token audience (defaults to client_id if not set)")
    
    # Automatically constructed URLs (computed properties)
    @property
    def issuer_url(self) -> Optional[str]:
        if self.domain:
            # Handle domain with or without https:// prefix
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}"
        return None
    
    @property
    def authorization_server_url(self) -> Optional[str]:
        """Authorization server base URL."""
        return self.issuer_url
    
    @property
    def authorization_endpoint(self) -> Optional[str]:
        if self.domain:
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}/v1/authorize"
        return None
    
    @property
    def token_endpoint(self) -> Optional[str]:
        if self.domain:
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}/v1/token"
        return None
    
    @property
    def introspect_endpoint(self) -> Optional[str]:
        if self.domain:
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}/v1/introspect"
        return None
    
    @property
    def jwks_uri(self) -> Optional[str]:
        if self.domain:
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}/v1/keys"
        return None
    
    @property
    def userinfo_endpoint(self) -> Optional[str]:
        if self.domain:
            domain = self.domain.replace('https://', '') if self.domain.startswith('https://') else self.domain
            return f"https://{domain}/oauth2/{self.authorization_server_id}/v1/userinfo"
        return None





class AuthenticationSettings(BaseSettings):
    """Main authentication settings for Okta OAuth2 provider."""
    
    model_config = SettingsConfigDict(
        env_prefix="MCP_AUTH_",
        env_nested_delimiter="__",
        case_sensitive=False
    )
    
    enabled: bool = Field(False, description="Enable OAuth2 authentication globally")
    provider: ProviderType = Field(ProviderType.DISABLED, description="OAuth2 provider to use")
    config_file: Optional[str] = Field("auth_config.json", description="Path to auth configuration file")
    
    # Provider-specific settings
    okta: OktaSettings = Field(default_factory=OktaSettings)
    
    def __init__(self, config_file: Optional[str] = None, **kwargs):
        """
        Initialize authentication settings.
        
        Priority order (highest to lowest):
        1. Explicit kwargs parameters
        2. Environment variables (MCP_AUTH_*)
        3. Configuration file (auth_config.json)
        4. Default values
        """
        # Load from config file first
        config_path = config_file or kwargs.pop('config_file', None) or "auth_config.json"
        file_config = load_auth_config_from_file(config_path)
        
        # Merge file config with kwargs (kwargs take precedence)
        merged_config = {**file_config, **kwargs}
        
        # Handle provider-specific settings from file config
        if file_config:
            if 'okta' in file_config and 'okta' not in kwargs:
                provider_config = file_config['okta']
                merged_config['okta'] = OktaSettings.from_config_dict(provider_config)
        
        super().__init__(**merged_config)
    
    def is_enabled(self) -> bool:
        """Check if OAuth2 authentication is enabled."""
        return self.enabled and self.provider != ProviderType.DISABLED
    
    def get_provider_settings(self) -> Optional[BaseOAuth2Settings]:
        """Get settings for the active provider."""
        if self.provider == ProviderType.OKTA:
            return self.okta
        return None


# Environment variable examples for Okta configuration:
# MCP_AUTH_ENABLED=true
# MCP_AUTH_PROVIDER=okta
# MCP_AUTH_OKTA__DOMAIN=dev-12345.okta.com
# MCP_AUTH_OKTA__CLIENT_ID=your_client_id
# MCP_AUTH_OKTA__CLIENT_SECRET=your_client_secret
# MCP_AUTH_OKTA__AUTHORIZATION_SERVER_ID=default
# MCP_AUTH_OKTA__AUDIENCE=api://your-api
# MCP_AUTH_OKTA__SCOPES=["openid", "profile", "email"]
