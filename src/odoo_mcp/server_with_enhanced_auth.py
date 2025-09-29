"""
Server with enhanced OAuth authentication including proactive refresh token management.

This server starts and stops background tasks for token management when the application
starts and shuts down.
"""

import asyncio
import atexit
from contextlib import asynccontextmanager

try:
    from .server import mcp as base_mcp
except ImportError:
    from src.odoo_mcp.server import mcp as base_mcp

try:
    from ..auth.auth_factory import AuthProviderFactory
    from ..auth.enhanced_okta_provider import EnhancedOktaProvider
except ImportError:
    from src.auth.auth_factory import AuthProviderFactory
    from src.auth.enhanced_okta_provider import EnhancedOktaProvider


# Global reference to enhanced provider for lifecycle management
enhanced_provider = None


@asynccontextmanager
async def enhanced_auth_lifespan(app):
    """Enhanced lifespan manager that handles auth provider lifecycle."""
    global enhanced_provider

    # Get the existing lifespan context (odoo client)
    async with base_mcp.lifespan(app) as context:

        # Start enhanced provider background tasks if applicable
        if enhanced_provider and isinstance(enhanced_provider, EnhancedOktaProvider):
            print("🚀 Starting enhanced OAuth background tasks...")
            await enhanced_provider.start_background_tasks()

        try:
            yield context
        finally:
            # Stop enhanced provider background tasks
            if enhanced_provider and isinstance(enhanced_provider, EnhancedOktaProvider):
                print("🛑 Stopping enhanced OAuth background tasks...")
                await enhanced_provider.stop_background_tasks()


# Create auth provider
auth_provider = AuthProviderFactory.create_provider_from_config()

if auth_provider:
    enhanced_provider = auth_provider  # Store reference for lifecycle management
    base_mcp.auth = auth_provider

    # Update lifespan to include auth provider management
    base_mcp.lifespan = enhanced_auth_lifespan

    if isinstance(auth_provider, EnhancedOktaProvider):
        print("🔒 Enhanced OAuth Provider configured with proactive token management")
        print("   ✓ Proactive token refresh enabled")
        print("   ✓ Connection health monitoring enabled")
        print("   ✓ Automatic token cleanup enabled")
    else:
        print("🔒 Standard OAuth Provider configured")
else:
    print("⚠️  OAuth not configured. Configure in auth_config.json or set environment variables")


# Add connection stats endpoint for monitoring
@base_mcp.tool(description="Get OAuth connection statistics")
def get_oauth_stats(ctx) -> dict:
    """Get OAuth connection statistics for monitoring."""
    if enhanced_provider and isinstance(enhanced_provider, EnhancedOktaProvider):
        return enhanced_provider.get_connection_stats()
    else:
        return {"message": "Enhanced OAuth not enabled"}


mcp = base_mcp