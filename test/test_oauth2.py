"""
Test script for OAuth2 authentication implementation.

This script tests the OAuth2 components without requiring a full Okta setup.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# Add the source directory to Python path
sys.path.insert(0, '/Users/thanhnguyen/Dev/Training/AI/MCP/mcp-odoo-http-streamable/src')

try:
    from odoo_mcp.auth import (
        AuthenticationSettings,
        OktaSettings,
        ProviderType,
        create_oauth2_provider,
        create_mcp_token_verifier,
        OAuth2ProviderFactory
    )
    print("✅ Successfully imported OAuth2 authentication components")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


def test_settings_configuration():
    """Test OAuth2 settings configuration"""
    print("\n=== Testing Settings Configuration ===")
    
    # Test default settings (disabled)
    settings = AuthenticationSettings()
    print(f"Default enabled: {settings.is_enabled()}")
    print(f"Default provider: {settings.provider}")
    
    # Test environment variable override
    os.environ["MCP_AUTH_ENABLED"] = "true"
    os.environ["MCP_AUTH_PROVIDER"] = "okta"
    os.environ["MCP_AUTH_OKTA_DOMAIN"] = "test-domain.okta.com"
    os.environ["MCP_AUTH_OKTA_CLIENT_ID"] = "test-client-id"
    
    # Reload settings with environment variables
    settings = AuthenticationSettings()
    print(f"With env vars enabled: {settings.is_enabled()}")
    print(f"With env vars provider: {settings.provider}")
    print(f"Okta domain: {settings.okta.domain}")
    print(f"Okta client ID: {settings.okta.client_id}")
    
    # Test programmatic configuration
    manual_settings = AuthenticationSettings(
        enabled=True,
        provider=ProviderType.OKTA,
        okta=OktaSettings(
            domain="manual-domain.okta.com",
            client_id="manual-client-id",
            audience="api://manual-api"
        )
    )
    print(f"Manual settings enabled: {manual_settings.is_enabled()}")
    print(f"Manual Okta domain: {manual_settings.okta.domain}")
    print(f"Manual audience: {manual_settings.okta.audience}")
    
    return settings


def test_factory_creation(settings: AuthenticationSettings):
    """Test OAuth2 provider factory"""
    print("\n=== Testing Provider Factory ===")
    
    # Test provider creation
    provider = OAuth2ProviderFactory.create_provider(settings)
    print(f"Provider created: {provider is not None}")
    print(f"Provider type: {type(provider).__name__ if provider else 'None'}")
    
    # Test MCP token verifier creation
    token_verifier = OAuth2ProviderFactory.create_token_verifier(settings)
    print(f"Token verifier created: {token_verifier is not None}")
    print(f"Token verifier type: {type(token_verifier).__name__ if token_verifier else 'None'}")
    
    # Test convenience functions
    provider2 = create_oauth2_provider(settings)
    token_verifier2 = create_mcp_token_verifier(settings)
    print(f"Convenience functions work: {provider2 is not None and token_verifier2 is not None}")
    
    return provider


async def test_provider_functionality(provider):
    """Test OAuth2 provider basic functionality"""
    print("\n=== Testing Provider Functionality ===")
    
    if not provider:
        print("❌ No provider available for testing")
        return
    
    # Test with invalid token (should fail gracefully)
    fake_token = "fake.jwt.token"
    
    try:
        result = await provider.validate_token(fake_token)
        print(f"Fake token validation result: {result.is_valid}")
        print(f"Fake token error: {result.error}")
    except Exception as e:
        print(f"Expected error for fake token: {e}")
    
    # Test endpoint discovery (if it works)
    try:
        if hasattr(provider, 'discover_endpoints'):
            endpoints = await provider.discover_endpoints()
            print(f"Endpoint discovery successful: {bool(endpoints)}")
        else:
            print("Provider doesn't support endpoint discovery")
    except Exception as e:
        print(f"Endpoint discovery error (expected): {e}")


def test_disabled_authentication():
    """Test behavior when authentication is disabled"""
    print("\n=== Testing Disabled Authentication ===")
    
    # Clear environment variables
    os.environ.pop("MCP_AUTH_ENABLED", None)
    
    settings = AuthenticationSettings()
    print(f"Authentication disabled: {not settings.is_enabled()}")
    
    provider = create_oauth2_provider(settings)
    print(f"Provider is None when disabled: {provider is None}")
    
    token_verifier = create_mcp_token_verifier(settings)
    print(f"Token verifier is None when disabled: {token_verifier is None}")


def test_integration_components():
    """Test integration components"""
    print("\n=== Testing Integration Components ===")
    
    try:
        from odoo_mcp.auth.middleware import (
            OAuth2Middleware,
            OAuth2AuthenticationError,
            FastMCPOAuth2Integration,
            create_oauth2_fastmcp_integration
        )
        print("✅ Successfully imported middleware components")
        
        # Test integration creation
        settings = AuthenticationSettings(enabled=False)  # Disabled for testing
        integration = create_oauth2_fastmcp_integration(settings)
        print(f"Integration created: {integration is not None}")
        print(f"Integration enabled: {integration.is_enabled()}")
        
        # Test FastMCP settings (should be None when disabled)
        fastmcp_settings = integration.get_fastmcp_auth_settings()
        print(f"FastMCP settings when disabled: {fastmcp_settings is None}")
        
    except ImportError as e:
        print(f"❌ Middleware import error: {e}")


def test_environment_variable_loading():
    """Test comprehensive environment variable loading"""
    print("\n=== Testing Environment Variable Loading ===")
    
    # Set comprehensive environment variables
    env_vars = {
        "MCP_AUTH_ENABLED": "true",
        "MCP_AUTH_PROVIDER": "okta",
        "MCP_AUTH_OKTA_DOMAIN": "env-test.okta.com",
        "MCP_AUTH_OKTA_CLIENT_ID": "env-client-id",
        "MCP_AUTH_OKTA_CLIENT_SECRET": "env-client-secret",
        "MCP_AUTH_OKTA_AUDIENCE": "api://env-api",
        "MCP_AUTH_OKTA_JWKS_CACHE_TTL": "7200",
        "MCP_AUTH_OKTA_VALIDATION_METHOD": "jwt"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    settings = AuthenticationSettings()
    
    print(f"Enabled: {settings.enabled}")
    print(f"Provider: {settings.provider}")
    print(f"Okta domain: {settings.okta.domain}")
    print(f"Okta client ID: {settings.okta.client_id}")
    print(f"Okta client secret set: {'***' if settings.okta.client_secret else 'No'}")
    print(f"Okta audience: {settings.okta.audience}")
    print(f"JWKS cache TTL: {settings.okta.jwks_cache_ttl}")
    print(f"Validation method: {settings.okta.validation_method}")
    
    # Test computed properties
    print(f"Authorization server URL: {settings.okta.authorization_server_url}")
    print(f"Token endpoint: {settings.okta.token_endpoint}")
    print(f"JWKS URI: {settings.okta.jwks_uri}")
    print(f"Userinfo endpoint: {settings.okta.userinfo_endpoint}")


async def main():
    """Main test function"""
    print("🔐 OAuth2 Authentication Implementation Test")
    print("=" * 50)
    
    # Test 1: Settings configuration
    settings = test_settings_configuration()
    
    # Test 2: Factory creation
    provider = test_factory_creation(settings)
    
    # Test 3: Provider functionality
    await test_provider_functionality(provider)
    
    # Test 4: Disabled authentication
    test_disabled_authentication()
    
    # Test 5: Integration components
    test_integration_components()
    
    # Test 6: Environment variable loading
    test_environment_variable_loading()
    
    print("\n" + "=" * 50)
    print("✅ OAuth2 implementation test completed!")
    print("\nNext steps:")
    print("1. Set up an Okta application")
    print("2. Configure environment variables with real Okta settings")
    print("3. Test with real OAuth2 tokens")
    print("4. Integrate with your MCP server")


if __name__ == "__main__":
    asyncio.run(main())
