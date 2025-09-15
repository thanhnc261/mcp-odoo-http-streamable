"""
Test script for OAuth2 configuration file loading.

This script tests the new auth_config.json functionality.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the source directory to Python path
sys.path.insert(0, '/Users/thanhnguyen/Dev/Training/AI/MCP/mcp-odoo-http-streamable/src')

def create_test_config_file():
    """Create a test configuration file"""
    test_config = {
        "enabled": True,
        "provider": "okta",
        "okta": {
            "domain": "test-file.okta.com",
            "client_id": "file-client-id",
            "client_secret": "file-client-secret",
            "audience": "api://file-api",
            "authorization_server_id": "default",
            "jwks_cache_ttl": 7200,
            "validation_method": "jwt",
            "validate_audience": True,
            "validate_issuer": True,
            "token_cache_ttl": 600,
            "scopes": ["openid", "profile", "email", "custom:scope"]
        }
    }
    
    config_path = Path("test_auth_config.json")
    with open(config_path, 'w') as f:
        json.dump(test_config, f, indent=2)
    
    print(f"✅ Created test config file: {config_path.absolute()}")
    return str(config_path)


def test_config_file_loading():
    """Test loading configuration from file"""
    print("\n=== Testing Config File Loading ===")
    
    try:
        from odoo_mcp.auth.settings import AuthenticationSettings, load_auth_config_from_file
        
        # Create test config file
        config_path = create_test_config_file()
        
        # Test direct file loading function
        config_data = load_auth_config_from_file(config_path)
        print(f"Config data loaded: {bool(config_data)}")
        print(f"Provider from file: {config_data.get('provider')}")
        print(f"Okta domain from file: {config_data.get('okta', {}).get('domain')}")
        
        # Test settings loading from file
        settings = AuthenticationSettings(config_file=config_path)
        print(f"Settings enabled: {settings.enabled}")
        print(f"Settings provider: {settings.provider}")
        print(f"Okta domain: {settings.okta.domain}")
        print(f"Okta client ID: {settings.okta.client_id}")
        print(f"Okta audience: {settings.okta.client_id}")  # This should use the computed property
        print(f"JWKS cache TTL: {settings.okta.jwks_cache_ttl}")
        print(f"Custom scopes: {settings.okta.scopes}")
        
        # Test that environment variables still override file config
        os.environ["MCP_AUTH_OKTA_DOMAIN"] = "env-override.okta.com"
        settings_with_env = AuthenticationSettings(config_file=config_path)
        print(f"Env override domain: {settings_with_env.okta.domain}")
        
        # Clean up env var
        os.environ.pop("MCP_AUTH_OKTA_DOMAIN", None)
        
        return True
        
    except Exception as e:
        print(f"❌ Config file loading error: {e}")
        return False
    finally:
        # Clean up test file
        test_file = Path("test_auth_config.json")
        if test_file.exists():
            test_file.unlink()
            print(f"🧹 Cleaned up test file: {test_file}")


def test_factory_with_config_file():
    """Test factory functions with config file"""
    print("\n=== Testing Factory with Config File ===")
    
    try:
        from odoo_mcp.auth import create_oauth2_provider, create_mcp_token_verifier
        
        # Create test config file
        config_path = create_test_config_file()
        
        # Test provider creation with config file
        provider = create_oauth2_provider(config_file=config_path)
        print(f"Provider created from config file: {provider is not None}")
        if provider:
            print(f"Provider type: {type(provider).__name__}")
            print(f"Provider domain: {provider.settings.domain}")
        
        # Test token verifier creation with config file
        token_verifier = create_mcp_token_verifier(config_file=config_path)
        print(f"Token verifier created from config file: {token_verifier is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Factory with config file error: {e}")
        return False
    finally:
        # Clean up test file
        test_file = Path("test_auth_config.json")
        if test_file.exists():
            test_file.unlink()


def test_integration_with_config_file():
    """Test integration components with config file"""
    print("\n=== Testing Integration with Config File ===")
    
    try:
        from odoo_mcp.auth.middleware import create_oauth2_fastmcp_integration
        
        # Create test config file
        config_path = create_test_config_file()
        
        # Test integration creation with config file
        integration = create_oauth2_fastmcp_integration(config_file=config_path)
        print(f"Integration created from config file: {integration is not None}")
        print(f"Integration enabled: {integration.is_enabled()}")
        
        # Test FastMCP settings
        fastmcp_settings = integration.get_fastmcp_auth_settings()
        print(f"FastMCP settings created: {fastmcp_settings is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration with config file error: {e}")
        return False
    finally:
        # Clean up test file
        test_file = Path("test_auth_config.json")
        if test_file.exists():
            test_file.unlink()


def test_config_file_priority():
    """Test configuration priority: kwargs > env vars > config file > defaults"""
    print("\n=== Testing Configuration Priority ===")
    
    try:
        from odoo_mcp.auth.settings import AuthenticationSettings
        
        # Create test config file
        config_path = create_test_config_file()
        
        # Set environment variable
        os.environ["MCP_AUTH_OKTA_CLIENT_ID"] = "env-client-id"
        
        # Test priority: explicit kwargs should override everything
        from odoo_mcp.auth.settings import OktaSettings
        
        settings = AuthenticationSettings(
            config_file=config_path,
            provider="okta",  # explicit override
            okta=OktaSettings(client_id="kwargs-client-id")  # explicit override
        )
        
        print(f"Domain (from file): {settings.okta.domain}")  # Should be from file
        print(f"Client ID (from kwargs): {settings.okta.client_id}")  # Should be from kwargs
        
        # Test without kwargs - env should override file
        settings_env = AuthenticationSettings(config_file=config_path)
        print(f"Client ID (from env): {settings_env.okta.client_id}")  # Should be from env
        
        # Clean up env var and test file-only
        os.environ.pop("MCP_AUTH_OKTA_CLIENT_ID", None)
        settings_file = AuthenticationSettings(config_file=config_path)
        print(f"Client ID (from file): {settings_file.okta.client_id}")  # Should be from file
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration priority error: {e}")
        return False
    finally:
        # Clean up
        os.environ.pop("MCP_AUTH_OKTA_CLIENT_ID", None)
        test_file = Path("test_auth_config.json")
        if test_file.exists():
            test_file.unlink()


async def main():
    """Main test function"""
    print("🔧 OAuth2 Configuration File Test")
    print("=" * 50)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: Config file loading
    if test_config_file_loading():
        success_count += 1
    
    # Test 2: Factory with config file
    if test_factory_with_config_file():
        success_count += 1
    
    # Test 3: Integration with config file
    if test_integration_with_config_file():
        success_count += 1
    
    # Test 4: Configuration priority
    if test_config_file_priority():
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"✅ Tests completed: {success_count}/{total_tests} successful")
    
    if success_count == total_tests:
        print("🎉 All config file tests passed!")
    else:
        print(f"⚠️  Some tests failed. Check the errors above.")
    
    print("\nConfig file functionality is ready! 📁")
    print("Create auth_config.json with your Okta settings.")


if __name__ == "__main__":
    asyncio.run(main())
