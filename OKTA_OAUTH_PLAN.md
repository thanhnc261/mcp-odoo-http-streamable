# Okta OAuth2 Integration Plan for MCP Odoo Server

## Executive Summary

This document outlines a comprehensive plan to implement OAuth2 authentication using Okta as the authorization server for the MCP Odoo HTTP server. The implementation will support HTTP streamable transport while maintaining minimal changes to Odoo interaction logic.

## Current State Analysis

### Current Implementation (FastMCP v2.12.3)
- **Framework**: FastMCP v2.12.3 with Streamable-HTTP transport
- **Auth Method**: Custom RemoteAuthProvider with manual OAuth discovery endpoints
- **Issues**:
  - Complex custom implementation with manual endpoint management
  - Client connectivity issues (Claude Desktop can't reach localhost)
  - Random client_id generation despite DCR mitigation attempts
  - Manual route management for OAuth discovery endpoints

### FastMCP Version Assessment
- **Current**: 2.12.3
- **Target**: 2.12.4+ (includes Auth0Provider which can be adapted for Okta)
- **Recommendation**: Upgrade to latest version for better OAuth provider support

## OAuth Provider Analysis

### Provider Compatibility Assessment

| Provider Type | DCR Support | FastMCP Support | Recommendation |
|---------------|-------------|-----------------|----------------|
| **Auth0Provider** | ✅ Yes | ✅ Native (v2.12.4+) | ⭐ Recommended |
| **RemoteAuthProvider** | ✅ Required | ✅ Yes | ⚠️ Current approach |
| **OAuthProxy** | ❌ No | ✅ Yes | ❌ Not suitable for Okta |

### Okta Classification
- **DCR Support**: ✅ Yes (RFC 7591 compliant)
- **OIDC Compliance**: ✅ Yes (.well-known/openid-configuration)
- **Best Match**: Auth0Provider pattern (OIDC Proxy approach)

## Recommended Implementation Strategy

### Phase 1: Migration to Auth0Provider Pattern

Since Okta supports OIDC and DCR like Auth0, we should leverage the Auth0Provider implementation pattern:

#### 1.1 FastMCP Upgrade
```bash
pip install fastmcp>=2.12.4
```

#### 1.2 Implementation Approach
Use Auth0Provider as a template to create `OktaProvider`:

```python
from fastmcp.server.auth.providers.auth0 import Auth0Provider

# Option A: Extend Auth0Provider for Okta
class OktaProvider(Auth0Provider):
    def __init__(self, config_url: str, client_id: str, client_secret: str,
                 audience: str, base_url: str):
        super().__init__(config_url, client_id, client_secret, audience, base_url)

# Option B: Use Auth0Provider directly (if compatible)
auth_provider = Auth0Provider(
    config_url="https://trial-2386786.okta.com/oauth2/default/.well-known/openid-configuration",
    client_id="0oave50up5LREJK5n697",
    client_secret="<required_for_auth0_provider>",
    audience="api://default",
    base_url="https://your-server.domain.com"
)
```

#### 1.3 Configuration Update

**fastmcp.json**:
```json
{
  "auth": {
    "provider": "okta",
    "okta": {
      "config_url": "https://trial-2386786.okta.com/oauth2/default/.well-known/openid-configuration",
      "client_id": "0oave50up5LREJK5n697",
      "client_secret": "${OKTA_CLIENT_SECRET}",
      "audience": "api://default",
      "base_url": "https://your-server.domain.com"
    }
  }
}
```

### Phase 2: Streamlined Server Implementation

#### 2.1 Simplified Server Code
```python
# server_with_auth.py
from fastmcp import FastMCP
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from .server import mcp as base_mcp

# Load configuration
config = load_config()
okta_config = config.get("auth", {}).get("okta", {})

if okta_config:
    auth_provider = Auth0Provider(
        config_url=okta_config["config_url"],
        client_id=okta_config["client_id"],
        client_secret=okta_config["client_secret"],
        audience=okta_config["audience"],
        base_url=okta_config["base_url"]
    )
    base_mcp.auth = auth_provider

mcp = base_mcp
```

#### 2.2 Remove Custom OAuth Routes
- Delete all custom `@base_mcp.custom_route` OAuth discovery endpoints
- Remove fake DCR endpoints
- Let FastMCP handle OAuth discovery automatically

## Client Compatibility Analysis

### Claude Desktop Discovery Flow
1. **Discovery Request**: `GET /.well-known/oauth-protected-resource/mcp`
2. **Auth Server Metadata**: `GET /.well-known/oauth-authorization-server`
3. **Client Registration**: Uses DCR or static configuration
4. **Authorization**: Redirects to Okta authorization endpoint
5. **Token Exchange**: Exchanges authorization code for access token

### MCP Inspector Tool Flow
Similar to Claude Desktop but may have different discovery endpoint preferences.

### Testing Requirements by Client

| Client | Discovery Endpoint | DCR Support | Static Client | Testing Notes |
|--------|-------------------|-------------|---------------|---------------|
| Claude Desktop | `/.well-known/oauth-protected-resource/mcp` | ✅ | ✅ | Requires HTTPS in production |
| MCP Inspector | `/.well-known/oauth-authorization-server` | ✅ | ✅ | Can work with localhost |
| Browser Tools | Standard OIDC endpoints | ✅ | ✅ | Requires CORS support |

## Deployment Architecture

### Development Environment
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │────│  MCP Server      │────│  Okta Tenant    │
│ (Claude Desktop)│    │ (localhost:8000) │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────────┐
                       │   Odoo Server    │
                       │ (localhost:10018)│
                       └──────────────────┘
```

### Production Environment
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │────│  MCP Server      │────│  Okta Tenant    │
│ (Claude Desktop)│    │ (HTTPS domain)   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────────┐
                       │   Odoo Server    │
                       │ (Internal/VPN)   │
                       └──────────────────┘
```

## Security Considerations

### 1. Client Authentication
- **Public Clients**: Use PKCE for Claude Desktop
- **Confidential Clients**: Use client_secret for server-to-server
- **Token Validation**: JWT signature verification with Okta JWKS

### 2. Network Security
- **HTTPS Required**: Production must use HTTPS
- **CORS Configuration**: Proper origin restrictions
- **Token Scoping**: Minimal required scopes (mcp:access)

### 3. Okta Configuration
```json
{
  "application_type": "web",
  "grant_types": ["authorization_code"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none",
  "require_auth_time": false,
  "require_pushed_authorization_requests": false
}
```

## Implementation Steps

### Step 1: Environment Preparation
1. Upgrade FastMCP to v2.12.4+
2. Set up HTTPS domain (ngrok for testing, proper SSL for production)
3. Configure Okta application with new redirect URIs

### Step 2: Code Refactoring
1. Create `OktaProvider` based on `Auth0Provider`
2. Simplify `server_with_auth.py` by removing custom routes
3. Update configuration in `fastmcp.json`
4. Update environment variables

### Step 3: Testing Strategy
1. **Unit Tests**: OAuth provider initialization and token validation
2. **Integration Tests**: MCP Inspector tool connectivity
3. **E2E Tests**: Claude Desktop OAuth flow
4. **Performance Tests**: Token validation latency

### Step 4: Production Deployment
1. Deploy to HTTPS-enabled environment
2. Update Okta redirect URIs to production domain
3. Configure environment variables securely
4. Monitor OAuth flows and error rates

## Migration Benefits

### Immediate Benefits
- **Simplified Codebase**: Remove 200+ lines of custom OAuth code
- **Better Compatibility**: Native FastMCP OAuth support
- **Automatic Updates**: OAuth improvements in FastMCP updates
- **Standard Compliance**: Full OAuth 2.1 and OIDC compliance

### Long-term Benefits
- **Maintainability**: Less custom code to maintain
- **Scalability**: Built-in FastMCP optimizations
- **Security**: Regular security updates from FastMCP team
- **Documentation**: Standard FastMCP OAuth patterns

## Risk Assessment

### Low Risk
- ✅ Okta OIDC compatibility with Auth0Provider pattern
- ✅ FastMCP OAuth provider framework stability
- ✅ Minimal changes to Odoo interaction logic

### Medium Risk
- ⚠️ Client connectivity during development (localhost limitations)
- ⚠️ HTTPS certificate management for production
- ⚠️ Okta client_secret management for confidential clients

### High Risk
- ❌ Breaking changes in FastMCP OAuth providers between versions
- ❌ Claude Desktop OAuth implementation changes
- ❌ Network connectivity issues in production environment

## Success Metrics

### Technical Metrics
- **OAuth Success Rate**: >99% successful authentications
- **Token Validation Latency**: <100ms average
- **Discovery Response Time**: <50ms for .well-known endpoints
- **Error Rate**: <1% OAuth-related errors

### Business Metrics
- **Client Compatibility**: 100% support for Claude Desktop and MCP Inspector
- **Development Velocity**: 50% reduction in OAuth-related development time
- **Security Compliance**: Full OAuth 2.1 and OIDC compliance
- **Maintainability Score**: Reduced custom OAuth code by 80%

## Conclusion

The migration from custom RemoteAuthProvider to Auth0Provider-based Okta integration represents a significant improvement in code quality, maintainability, and compliance. By leveraging FastMCP's built-in OAuth capabilities and following established patterns, we can achieve a more robust and future-proof authentication implementation while maintaining full compatibility with MCP clients.

The key success factor is ensuring proper HTTPS deployment for production use, as this resolves the primary connectivity issues experienced during development with localhost-based testing.

---

**Document Version**: 1.0
**Last Updated**: 2025-09-17
**Author**: Claude (Anthropic)
**Status**: Draft - Ready for Review