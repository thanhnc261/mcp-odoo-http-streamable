"""
Session management for OAuth2 MCP server.
Handles tracking of active Claude Desktop sessions and token lifecycle.
"""

import logging
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Information about an active Claude Desktop session."""
    
    client_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    scopes: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    user_info: Optional[Dict] = None
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def update_last_seen(self):
        """Update the last seen timestamp."""
        self.last_seen = time.time()


class SessionManager:
    """Manages active OAuth2 sessions for Claude Desktop clients."""
    
    def __init__(self):
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.revoked_tokens: Set[str] = set()
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def create_session(self, client_id: str, access_token: str, refresh_token: Optional[str] = None,
                      expires_in: Optional[int] = None, scopes: Optional[Set[str]] = None,
                      user_info: Optional[Dict] = None) -> SessionInfo:
        """Create a new session for a Claude Desktop client."""
        with self._lock:
            expires_at = None
            if expires_in:
                expires_at = time.time() + expires_in
            
            session = SessionInfo(
                client_id=client_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scopes=scopes or set(),
                user_info=user_info
            )
            
            self.active_sessions[client_id] = session
            logger.info(f"Created session for client {client_id}")
            return session
    
    def get_session(self, client_id: str) -> Optional[SessionInfo]:
        """Get session information for a client."""
        with self._lock:
            session = self.active_sessions.get(client_id)
            if session and not session.is_expired():
                session.update_last_seen()
                return session
            elif session and session.is_expired():
                # Clean up expired session
                self.remove_session(client_id)
            return None
    
    def get_session_by_token(self, access_token: str) -> Optional[SessionInfo]:
        """Get session information by access token."""
        with self._lock:
            for session in self.active_sessions.values():
                if session.access_token == access_token and not session.is_expired():
                    session.update_last_seen()
                    return session
            return None
    
    def update_session_tokens(self, client_id: str, access_token: str, 
                            refresh_token: Optional[str] = None, expires_in: Optional[int] = None):
        """Update session tokens (for token refresh)."""
        with self._lock:
            session = self.active_sessions.get(client_id)
            if session:
                # Revoke old access token
                self.revoked_tokens.add(session.access_token)
                
                # Update with new tokens
                session.access_token = access_token
                if refresh_token:
                    session.refresh_token = refresh_token
                if expires_in:
                    session.expires_at = time.time() + expires_in
                
                session.update_last_seen()
                logger.info(f"Updated tokens for client {client_id}")
    
    def remove_session(self, client_id: str) -> bool:
        """Remove a session and revoke its tokens."""
        with self._lock:
            session = self.active_sessions.pop(client_id, None)
            if session:
                # Add tokens to revocation list
                self.revoked_tokens.add(session.access_token)
                if session.refresh_token:
                    self.revoked_tokens.add(session.refresh_token)
                
                logger.info(f"Removed session for client {client_id}")
                return True
            return False
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a specific token."""
        with self._lock:
            self.revoked_tokens.add(token)
            
            # Find and remove session with this token
            for client_id, session in list(self.active_sessions.items()):
                if session.access_token == token or session.refresh_token == token:
                    self.remove_session(client_id)
                    return True
            return False
    
    def is_token_revoked(self, token: str) -> bool:
        """Check if a token has been revoked."""
        with self._lock:
            return token in self.revoked_tokens
    
    def list_active_sessions(self) -> Dict[str, SessionInfo]:
        """Get all active sessions."""
        with self._lock:
            # Filter out expired sessions
            active = {}
            for client_id, session in self.active_sessions.items():
                if not session.is_expired():
                    active[client_id] = session
                else:
                    # Schedule for cleanup
                    self.remove_session(client_id)
            return active
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions and old revoked tokens."""
        with self._lock:
            current_time = time.time()
            
            # Remove expired sessions
            expired_clients = []
            for client_id, session in self.active_sessions.items():
                if session.is_expired():
                    expired_clients.append(client_id)
            
            for client_id in expired_clients:
                self.remove_session(client_id)
            
            # Clean up old revoked tokens (older than 24 hours)
            # Keep a reasonable cache to prevent token reuse
            if len(self.revoked_tokens) > 10000:  # Arbitrary limit
                logger.info("Cleaning up revoked tokens cache")
                # In production, you'd want a more sophisticated cleanup
                # For now, just clear half of them
                tokens_list = list(self.revoked_tokens)
                self.revoked_tokens = set(tokens_list[:5000])
            
            if expired_clients:
                logger.info(f"Cleaned up {len(expired_clients)} expired sessions")
    
    def _cleanup_worker(self):
        """Background worker to clean up expired sessions."""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                self.cleanup_expired_sessions()
                self._cleanup_stale_sessions()
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
    
    def _cleanup_stale_sessions(self):
        """Clean up sessions that haven't been used recently (Claude Desktop disconnections)."""
        with self._lock:
            current_time = time.time()
            stale_threshold = 1800  # 30 minutes of inactivity
            
            stale_clients = []
            for client_id, session in self.active_sessions.items():
                # Check if session hasn't been used in the last 30 minutes
                if current_time - session.last_seen > stale_threshold:
                    stale_clients.append(client_id)
            
            for client_id in stale_clients:
                logger.info(f"Cleaning up stale session for client {client_id} (inactive for {stale_threshold/60:.1f} minutes)")
                self.remove_session(client_id)
            
            if stale_clients:
                logger.info(f"Cleaned up {len(stale_clients)} stale sessions due to inactivity")


# Global session manager instance
session_manager = SessionManager()