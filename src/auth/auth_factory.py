import os
import json
from pathlib import Path
from typing import Optional
from .okta_provider import OktaProvider
from .enhanced_okta_provider import EnhancedOktaProvider


def load_config():
    """Load configuration from auth_config.json if available."""
    current_dir = Path(__file__).parent

    possible_paths = [
        Path("auth_config.json"),
        current_dir / "../../auth_config.json",
        current_dir.parent.parent / "auth_config.json",
    ]

    for config_path in possible_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                continue

    print("⚠️  No auth configuration found, using defaults.")
    return {}


class AuthProviderFactory:
    """Factory pattern implementation for creating Auth providers"""

    @staticmethod
    def create_provider_from_config() -> Optional[OktaProvider]:
        """
        Load configuration and create Auth provider

        Returns:
            Auth provider instance or None if not configured
        """
        config = load_config()
        auth_config = config.get("auth", {})

        auth_provider_type = auth_config.get("provider", "okta")
        auth_provider_config = auth_config.get("config", {})

        return AuthProviderFactory.create_provider(auth_provider_type, auth_provider_config)

    @staticmethod
    def create_provider(provider_type: str, config: dict) -> Optional[OktaProvider]:
        """
        Create an Auth provider based on provider type and configuration

        Args:
            provider_type: Type of provider ('okta', etc.)
            config: Configuration dictionary

        Returns:
            Auth provider instance or None if not configured
        """
        if provider_type.lower() == "okta":
            return AuthProviderFactory._create_okta_provider(config)
        else:
            raise ValueError(f"Unsupported auth provider type: {provider_type}")

    @staticmethod
    def _create_okta_provider(config: dict) -> Optional[OktaProvider]:
        """Create Okta provider from configuration"""

        # Get configuration from config file first, then fallback to environment
        domain = config.get("domain") or os.getenv("OKTA_DOMAIN")
        client_id = config.get("client_id") or os.getenv("OKTA_CLIENT_ID")
        client_secret = config.get("client_secret") or os.getenv("OKTA_CLIENT_SECRET")
        base_url = config.get("base_url", "http://localhost:8000")

        if not domain or not client_id:
            print("⚠️  Okta not configured. Required: domain, client_id")
            return None

        scopes = config.get("scopes", ["openid", "profile", "email", "mcp:access", "claudeai"])
        pkce = config.get("pkce", True)

        # Check if enhanced features are requested
        use_enhanced = config.get("enhanced", False)

        if use_enhanced:
            # Enhanced provider with proactive refresh and connection management
            enhanced_config = config.get("enhanced_config", {})

            return EnhancedOktaProvider(
                domain=domain,
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
                pkce=pkce,
                base_url=base_url,
                proactive_refresh_threshold=enhanced_config.get("proactive_refresh_threshold", 300),
                cleanup_interval=enhanced_config.get("cleanup_interval", 3600),
                connection_check_interval=enhanced_config.get("connection_check_interval", 1800)
            )
        else:
            # Standard provider
            return OktaProvider(
                domain=domain,
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
                pkce=pkce,
                base_url=base_url
            )