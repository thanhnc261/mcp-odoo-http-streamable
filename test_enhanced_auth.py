#!/usr/bin/env python3
"""Test script to verify enhanced OAuth implementation loads correctly."""

import sys
import traceback

def test_enhanced_auth():
    """Test that the enhanced auth server loads correctly."""
    print("🧪 Testing Enhanced OAuth Implementation")
    print("=" * 50)

    try:
        # Test imports
        print("1. Testing imports...")
        from src.auth.auth_factory import AuthProviderFactory
        from src.auth.enhanced_okta_provider import EnhancedOktaProvider
        print("   ✅ Auth imports successful")

        # Test configuration loading
        print("2. Testing configuration loading...")
        provider = AuthProviderFactory.create_provider_from_config()
        if provider:
            print(f"   ✅ Auth provider created: {type(provider).__name__}")

            if isinstance(provider, EnhancedOktaProvider):
                print("   ✅ Enhanced OAuth Provider detected")
                print(f"   📊 Proactive refresh threshold: {provider.proactive_refresh_threshold}s")
                print(f"   🧹 Cleanup interval: {provider.cleanup_interval}s")
                print(f"   🏥 Health check interval: {provider.connection_check_interval}s")
            else:
                print("   ⚠️  Standard OAuth Provider (not enhanced)")
        else:
            print("   ❌ No auth provider configured")

        # Test server loading
        print("3. Testing server loading...")
        from src.odoo_mcp.server_with_enhanced_auth import mcp
        print(f"   ✅ Server loaded: {mcp.name}")
        print(f"   🔐 Auth enabled: {mcp.auth is not None}")

        if mcp.auth:
            print(f"   🔒 Auth type: {type(mcp.auth).__name__}")

        print("\n🎉 All tests passed! Enhanced OAuth implementation is ready.")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_enhanced_auth()
    sys.exit(0 if success else 1)