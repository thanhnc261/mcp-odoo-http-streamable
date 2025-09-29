import os
from fastmcp.server.auth import OAuthProxy, JWTVerifier
from typing import List, Optional


class OktaProvider(OAuthProxy):
    """Custom OktaProvider that wraps OAuthProxy with Okta-specific configuration."""

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        pkce: bool = True,
        base_url: Optional[str] = None
    ):
        if scopes is None:
            scopes = ["openid", "profile", "email"]

        # Create JWT verifier for Okta with no audience validation
        # For dynamic client registration, audience validation is problematic
        # because each client gets a different audience in their tokens
        token_verifier = JWTVerifier(
            jwks_uri=f"{domain}/oauth2/default/v1/keys",
            issuer=f"{domain}/oauth2/default",
            audience=None  # Skip audience validation for dynamic registration
        )

        # Prepare authorize params
        extra_authorize_params = {"scope": " ".join(scopes)}
        if pkce:
            extra_authorize_params.update({
                "code_challenge_method": "S256"
            })

        # Handle empty or None client secret for PKCE-only flows
        if not client_secret:
            # For public clients using PKCE, we still need to provide a secret
            # Some OAuth implementations require this even for public clients
            client_secret = ""

        # Initialize parent OAuthProxy with Claude-compatible scopes and redirect URIs
        super().__init__(
            token_verifier=token_verifier,
            upstream_authorization_endpoint=f"{domain}/oauth2/default/v1/authorize",
            upstream_token_endpoint=f"{domain}/oauth2/default/v1/token",
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            base_url=base_url or "http://localhost:8002",
            extra_authorize_params=extra_authorize_params,
            valid_scopes=["openid", "profile", "email", "mcp:access", "claudeai"],
            allowed_client_redirect_uris=[
                "https://claude.ai/api/mcp/auth_callback",
                "https://chatgpt.com/oauth/callback"
            ]
        )

        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.pkce = pkce