#!/usr/bin/env python3
"""
Demo script to show OAuth statistics from the enhanced provider.
"""

def demo_oauth_stats():
    """Demonstrate OAuth statistics functionality."""
    print("📊 OAuth Connection Statistics Demo")
    print("=" * 40)

    try:
        # Import the enhanced server
        from src.odoo_mcp.server_with_enhanced_auth import mcp
        from src.auth.enhanced_okta_provider import EnhancedOktaProvider

        if mcp.auth and isinstance(mcp.auth, EnhancedOktaProvider):
            # Get OAuth statistics
            stats = mcp.auth.get_connection_stats()

            print("🔍 Current OAuth Statistics:")
            print("-" * 30)
            print(f"Active connections: {stats['active_connections']}")
            print(f"Total access tokens: {stats['total_access_tokens']}")
            print(f"Total refresh tokens: {stats['total_refresh_tokens']}")
            print(f"Background task running: {stats['background_task_running']}")

            if stats['connection_health']:
                print("\n🏥 Connection Health:")
                for client_id, health in stats['connection_health'].items():
                    print(f"  Client {client_id[:8]}...")
                    for key, value in health.items():
                        print(f"    {key}: {value}")
            else:
                print("\n🏥 No active connections yet")

            print(f"\n📋 Available OAuth tools:")
            print("  • get_oauth_stats - Get connection statistics")
            print("  • Automatic background tasks:")
            print(f"    - Proactive refresh: every 60s (threshold: {mcp.auth.proactive_refresh_threshold}s)")
            print(f"    - Token cleanup: every {mcp.auth.cleanup_interval}s")
            print(f"    - Health checks: every {mcp.auth.connection_check_interval}s")

        else:
            print("⚠️  Enhanced OAuth not enabled")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    demo_oauth_stats()