#!/usr/bin/env python3
"""
Run the enhanced OAuth MCP server with proactive token management.
"""

import asyncio
import os

# Set environment variables for Okta OAuth
os.environ["FASTMCP_AUTH_JWKS_URI"] = "https://trial-2386786.okta.com/oauth2/default/v1/keys"
os.environ["FASTMCP_AUTH_ISSUER"] = "https://trial-2386786.okta.com/oauth2/default"
os.environ["FASTMCP_AUTH_AUDIENCE"] = "api://default"
os.environ["FASTMCP_AUTH_CLIENT_ID"] = "0oave50up5LREJK5n697"

async def main():
    """Run the enhanced MCP server."""
    from src.odoo_mcp.server_with_enhanced_auth import mcp

    print("🚀 Starting Enhanced Odoo MCP Server with OAuth")
    print("=" * 50)
    print(f"Server: {mcp.name}")
    print(f"Auth enabled: {mcp.auth is not None}")

    if mcp.auth:
        print(f"Auth type: {type(mcp.auth).__name__}")

        # Check if it's enhanced
        from src.auth.enhanced_okta_provider import EnhancedOktaProvider
        if isinstance(mcp.auth, EnhancedOktaProvider):
            print("✨ Enhanced features enabled:")
            print(f"  • Proactive refresh: {mcp.auth.proactive_refresh_threshold}s before expiry")
            print(f"  • Cleanup interval: {mcp.auth.cleanup_interval}s")
            print(f"  • Health checks: {mcp.auth.connection_check_interval}s")

    print("\n🌐 Server will be available at:")
    print("  • HTTP: http://localhost:8000")
    print("  • OAuth stats: http://localhost:8000/oauth/stats")
    print("\nPress Ctrl+C to stop the server\n")

    # Run the server
    # await mcp.run(transport="http", host="localhost", port=8000)
    await mcp.run_http_async(host="0.0.0.0", port=8000, path="")

if __name__ == "__main__":
    asyncio.run(main())