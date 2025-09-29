#!/usr/bin/env python3
"""
Run Odoo MCP Server with HTTP transport for MCP inspector tools.
"""

import asyncio
import os
import sys

# Set default Odoo environment if not set
os.environ.setdefault('ODOO_URL', 'http://localhost:10018')
os.environ.setdefault('ODOO_DB', 'odoo18')
os.environ.setdefault('ODOO_USERNAME', 'admin')
os.environ.setdefault('ODOO_PASSWORD', 'admin')

from src.odoo_mcp.server_with_auth import mcp

async def main():
    """Run MCP server with HTTP transport."""
    print("=== ODOO MCP SERVER (HTTP) ===")

    print("\nPress Ctrl+C to stop")
    print("-" * 50)

    # Run HTTP server with root path
    await mcp.run_http_async(host="0.0.0.0", port=8000, path="")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)