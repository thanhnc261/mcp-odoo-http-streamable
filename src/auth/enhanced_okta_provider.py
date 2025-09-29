"""
Enhanced OktaProvider with proactive refresh token management and connection health monitoring.

This implementation adds:
1. Proactive token refresh before expiry
2. Connection health monitoring
3. Automatic cleanup of expired tokens
4. Graceful disconnection handling
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any

from fastmcp.server.auth import OAuthProxy, JWTVerifier
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


class EnhancedOktaProvider(OAuthProxy):
    """
    Enhanced OktaProvider with proactive refresh token management.

    Features:
    - Proactive token refresh (refreshes tokens 5 minutes before expiry)
    - Connection health monitoring
    - Automatic cleanup of expired tokens
    - Graceful disconnection when refresh fails
    """

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        pkce: bool = True,
        base_url: Optional[str] = None,
        # Enhanced configuration
        proactive_refresh_threshold: int = 300,  # Refresh 5 minutes before expiry
        cleanup_interval: int = 3600,  # Cleanup every hour
        connection_check_interval: int = 1800,  # Check connections every 30 minutes
    ):
        """
        Initialize enhanced Okta provider.

        Args:
            domain: Okta domain (e.g., https://dev-123.okta.com)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            scopes: OAuth scopes
            pkce: Enable PKCE
            base_url: Base URL for the server
            proactive_refresh_threshold: Seconds before expiry to proactively refresh (default: 5 minutes)
            cleanup_interval: Seconds between cleanup cycles (default: 1 hour)
            connection_check_interval: Seconds between connection health checks (default: 30 minutes)
        """

        if scopes is None:
            scopes = ["openid", "profile", "email", "mcp:access", "claudeai"]

        # Ensure domain has https:// prefix
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"

        # Create JWT verifier for Okta
        token_verifier = JWTVerifier(
            jwks_uri=f"{domain}/oauth2/default/v1/keys",
            issuer=f"{domain}/oauth2/default",
            audience="api://default"  # Standard Okta audience
        )

        # Handle empty or None client secret for PKCE-only flows
        if not client_secret:
            client_secret = ""

        # Initialize parent OAuthProxy
        super().__init__(
            token_verifier=token_verifier,
            upstream_authorization_endpoint=f"{domain}/oauth2/default/v1/authorize",
            upstream_token_endpoint=f"{domain}/oauth2/default/v1/token",
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            base_url=base_url or "http://localhost:8000",
            valid_scopes=scopes,
            allowed_client_redirect_uris=[
                "https://claude.ai/api/mcp/auth_callback",
                "https://chatgpt.com/oauth/callback",
                "http://localhost:*"  # Allow localhost with any port for development
            ],
            forward_pkce=pkce
        )

        # Enhanced configuration
        self.proactive_refresh_threshold = proactive_refresh_threshold
        self.cleanup_interval = cleanup_interval
        self.connection_check_interval = connection_check_interval

        # Enhanced state tracking
        self._connection_health: Dict[str, Dict[str, Any]] = {}  # client_id -> health info
        self._last_cleanup = time.time()
        self._last_connection_check = time.time()

        # Background task control
        self._background_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        logger.info(f"Enhanced Okta provider initialized for domain: {domain}")

    async def start_background_tasks(self):
        """Start background tasks for token management."""
        if self._background_task is None or self._background_task.done():
            self._shutdown_event.clear()
            self._background_task = asyncio.create_task(self._background_worker())
            logger.info("Started background token management tasks")

    async def stop_background_tasks(self):
        """Stop background tasks gracefully."""
        self._shutdown_event.set()
        if self._background_task and not self._background_task.done():
            try:
                await asyncio.wait_for(self._background_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._background_task.cancel()
                try:
                    await self._background_task
                except asyncio.CancelledError:
                    pass
            logger.info("Stopped background token management tasks")

    async def _background_worker(self):
        """Background worker for token management tasks."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    current_time = time.time()

                    # Proactive token refresh
                    await self._check_and_refresh_tokens()

                    # Cleanup expired tokens
                    if current_time - self._last_cleanup > self.cleanup_interval:
                        await self._cleanup_expired_tokens()
                        self._last_cleanup = current_time

                    # Check connection health
                    if current_time - self._last_connection_check > self.connection_check_interval:
                        await self._check_connection_health()
                        self._last_connection_check = current_time

                    # Wait before next check (every 60 seconds)
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60.0)

                except asyncio.TimeoutError:
                    # Normal timeout, continue loop
                    continue
                except Exception as e:
                    logger.error(f"Error in background worker: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Wait before retrying

        except asyncio.CancelledError:
            logger.info("Background worker cancelled")
            raise

    async def _check_and_refresh_tokens(self):
        """Check for tokens that need proactive refresh."""
        current_time = time.time()
        tokens_to_refresh = []

        # Find access tokens that need refresh
        for token_value, access_token in self._access_tokens.items():
            if access_token.expires_at:
                time_until_expiry = access_token.expires_at - current_time
                if 0 < time_until_expiry <= self.proactive_refresh_threshold:
                    # Token expires soon, check if we have a refresh token
                    refresh_token_value = self._access_to_refresh.get(token_value)
                    if refresh_token_value and refresh_token_value in self._refresh_tokens:
                        tokens_to_refresh.append((access_token, self._refresh_tokens[refresh_token_value]))

        # Perform proactive refresh
        for access_token, refresh_token in tokens_to_refresh:
            try:
                logger.info(f"Proactively refreshing token for client {access_token.client_id}")

                # Get client info
                client = await self.get_client(access_token.client_id)
                if client:
                    # Perform refresh
                    await self.exchange_refresh_token(
                        client, refresh_token, access_token.scopes
                    )

                    # Update connection health
                    self._connection_health[access_token.client_id] = {
                        "last_refresh": current_time,
                        "status": "healthy",
                        "refresh_count": self._connection_health.get(access_token.client_id, {}).get("refresh_count", 0) + 1
                    }

                    logger.info(f"Successfully refreshed token for client {access_token.client_id}")

            except Exception as e:
                logger.error(f"Failed to proactively refresh token for client {access_token.client_id}: {e}")

                # Mark connection as unhealthy
                self._connection_health[access_token.client_id] = {
                    "last_refresh_attempt": current_time,
                    "status": "unhealthy",
                    "error": str(e),
                    "failed_refresh_count": self._connection_health.get(access_token.client_id, {}).get("failed_refresh_count", 0) + 1
                }

                # Consider disconnecting if multiple failures
                failed_count = self._connection_health[access_token.client_id]["failed_refresh_count"]
                if failed_count >= 3:
                    logger.warning(f"Disconnecting client {access_token.client_id} after {failed_count} failed refresh attempts")
                    await self._disconnect_client(access_token.client_id)

    async def _cleanup_expired_tokens(self):
        """Remove expired tokens from storage."""
        current_time = time.time()
        expired_access_tokens = []
        expired_refresh_tokens = []

        # Find expired access tokens
        for token_value, access_token in self._access_tokens.items():
            if access_token.expires_at and access_token.expires_at < current_time:
                expired_access_tokens.append(token_value)

        # Find expired refresh tokens (if they have expiry)
        for token_value, refresh_token in self._refresh_tokens.items():
            if refresh_token.expires_at and refresh_token.expires_at < current_time:
                expired_refresh_tokens.append(token_value)

        # Clean up expired tokens
        for token_value in expired_access_tokens:
            access_token = self._access_tokens.pop(token_value, None)
            if access_token:
                # Also remove associated refresh token
                refresh_token_value = self._access_to_refresh.pop(token_value, None)
                if refresh_token_value:
                    self._refresh_tokens.pop(refresh_token_value, None)
                    self._refresh_to_access.pop(refresh_token_value, None)
                logger.debug(f"Cleaned up expired access token for client {access_token.client_id}")

        for token_value in expired_refresh_tokens:
            refresh_token = self._refresh_tokens.pop(token_value, None)
            if refresh_token:
                # Also remove associated access token
                access_token_value = self._refresh_to_access.pop(token_value, None)
                if access_token_value:
                    self._access_tokens.pop(access_token_value, None)
                    self._access_to_refresh.pop(access_token_value, None)
                logger.debug(f"Cleaned up expired refresh token for client {refresh_token.client_id}")

        if expired_access_tokens or expired_refresh_tokens:
            logger.info(f"Cleaned up {len(expired_access_tokens)} expired access tokens and {len(expired_refresh_tokens)} expired refresh tokens")

    async def _check_connection_health(self):
        """Check the health of all active connections."""
        current_time = time.time()

        # Get all active clients from access tokens
        active_clients = set(token.client_id for token in self._access_tokens.values())

        for client_id in active_clients:
            health_info = self._connection_health.get(client_id, {})

            # Check for stale connections (no activity for 24 hours)
            last_activity = max(
                health_info.get("last_refresh", 0),
                health_info.get("last_token_validation", 0)
            )

            if current_time - last_activity > 86400:  # 24 hours
                logger.warning(f"Stale connection detected for client {client_id}, considering cleanup")
                await self._disconnect_client(client_id)

            # Log connection health summary
            status = health_info.get("status", "unknown")
            refresh_count = health_info.get("refresh_count", 0)
            logger.debug(f"Client {client_id} health: {status}, refreshes: {refresh_count}")

    async def _disconnect_client(self, client_id: str):
        """Gracefully disconnect a client by cleaning up all tokens."""
        logger.info(f"Disconnecting client {client_id}")

        # Find and remove all tokens for this client
        tokens_to_remove = []
        for token_value, access_token in self._access_tokens.items():
            if access_token.client_id == client_id:
                tokens_to_remove.append(token_value)

        for token_value in tokens_to_remove:
            access_token = self._access_tokens.pop(token_value, None)
            if access_token:
                # Revoke the token if possible
                try:
                    await self.revoke_token(access_token)
                except Exception as e:
                    logger.warning(f"Failed to revoke token during disconnect: {e}")

                # Clean up associated refresh token
                refresh_token_value = self._access_to_refresh.pop(token_value, None)
                if refresh_token_value:
                    refresh_token = self._refresh_tokens.pop(refresh_token_value, None)
                    if refresh_token:
                        try:
                            await self.revoke_token(refresh_token)
                        except Exception as e:
                            logger.warning(f"Failed to revoke refresh token during disconnect: {e}")
                    self._refresh_to_access.pop(refresh_token_value, None)

        # Clean up connection health info
        self._connection_health.pop(client_id, None)

        logger.info(f"Client {client_id} disconnected and cleaned up")

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Enhanced token loading with health tracking."""
        result = await super().load_access_token(token)

        if result:
            # Update connection health with successful token validation
            current_time = time.time()
            if result.client_id not in self._connection_health:
                self._connection_health[result.client_id] = {}

            self._connection_health[result.client_id].update({
                "last_token_validation": current_time,
                "status": "healthy"
            })

        return result

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics for monitoring."""
        return {
            "active_connections": len(set(token.client_id for token in self._access_tokens.values())),
            "total_access_tokens": len(self._access_tokens),
            "total_refresh_tokens": len(self._refresh_tokens),
            "connection_health": dict(self._connection_health),
            "background_task_running": self._background_task is not None and not self._background_task.done()
        }