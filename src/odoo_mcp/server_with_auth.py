try:
    from .server import mcp as base_mcp
except ImportError:
    from src.odoo_mcp.server import mcp as base_mcp

try:
    from ..auth.auth_factory import AuthProviderFactory
except ImportError:
    from src.auth.auth_factory import AuthProviderFactory


auth_provider = AuthProviderFactory.create_provider_from_config()

if auth_provider:
    base_mcp.auth = auth_provider
    print("🔒 OAuth Provider configured")
else:
    print("⚠️  OAuth not configured. Configure in fastmcp.json or set environment variables")

mcp = base_mcp