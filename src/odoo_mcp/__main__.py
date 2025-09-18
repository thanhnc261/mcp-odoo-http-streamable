"""
Command line entry point for the Odoo MCP Server
"""
import sys
import asyncio
import traceback
import os

# Import the unified server that auto-detects auth configuration
from .server_with_auth import mcp


def main() -> int:
    """
    Run the unified MCP server (auto-detects auth configuration)
    """
    try:
        print("=== ODOO MCP SERVER (FastMCP v2.12.0) ===", file=sys.stderr)
        print(f"Python version: {sys.version}", file=sys.stderr)

        # Check if auth is configured
        auth_configured = all([
            os.getenv("FASTMCP_AUTH_JWKS_URI"),
            os.getenv("FASTMCP_AUTH_ISSUER"),
            os.getenv("FASTMCP_AUTH_AUDIENCE")
        ])

        if auth_configured:
            print("✅ OAuth authentication configured", file=sys.stderr)
            print(f"   Issuer: {os.getenv('FASTMCP_AUTH_ISSUER')}", file=sys.stderr)
            print(f"   Audience: {os.getenv('FASTMCP_AUTH_AUDIENCE')}", file=sys.stderr)
            client_id = os.getenv("FASTMCP_AUTH_CLIENT_ID")
            if client_id:
                print(f"   Client ID: {client_id}", file=sys.stderr)
            print("   🔒 Remote OAuth with built-in discovery endpoints", file=sys.stderr)
        else:
            print("ℹ️  No OAuth configuration found, running without authentication", file=sys.stderr)

        print(f"\nServer: {mcp.name}", file=sys.stderr)
        print(f"Auth enabled: {mcp.auth is not None}", file=sys.stderr)
        print(f"FastMCP version: 2.12.0", file=sys.stderr)

        print("\nEnvironment variables:", file=sys.stderr)
        for key, value in os.environ.items():
            if key.startswith(("ODOO_", "FASTMCP_AUTH_")):
                if "PASSWORD" in key or "SECRET" in key:
                    print(f"  {key}: ***hidden***", file=sys.stderr)
                else:
                    print(f"  {key}: {value}", file=sys.stderr)

        print("\nStarting MCP server...", file=sys.stderr)
        sys.stderr.flush()

        # Use the run() method directly
        mcp.run()
        
        # If execution reaches here, the server exited normally
        print("MCP server stopped normally", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("MCP server stopped by user", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        print("Exception details:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
