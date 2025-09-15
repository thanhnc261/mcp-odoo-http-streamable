"""
OAuth2 HTTP middleware for handling discovery endpoints.

Provides HTTP-level handlers for OAuth2 discovery endpoints as required
by the MCP OAuth2 specification. These endpoints need to be available
as HTTP routes, not MCP resources/tools.
"""

import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .discovery import OAuth2DiscoveryService
from .settings import AuthenticationSettings

logger = logging.getLogger(__name__)


class OAuth2HTTPMiddleware:
    """HTTP middleware for OAuth2 discovery endpoints."""
    
    def __init__(self, discovery_service: OAuth2DiscoveryService):
        self.discovery_service = discovery_service
    
    def should_handle_request(self, path: str) -> bool:
        """Check if this middleware should handle the request path."""
        oauth2_paths = [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-authorization-server", 
            "/register"
        ]
        return path in oauth2_paths
    
    def handle_request(self, method: str, path: str, headers: Dict[str, str], body: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Handle OAuth2 discovery HTTP request.
        
        Returns:
            Dictionary with 'status', 'headers', and 'body' keys
        """
        try:
            # Reconstruct request URL from headers
            host = headers.get("host", "localhost:8000")
            scheme = "https" if headers.get("x-forwarded-proto") == "https" else "http"
            request_url = f"{scheme}://{host}"
            
            if path == "/.well-known/oauth-protected-resource":
                return self._handle_protected_resource_metadata(request_url)
            elif path == "/.well-known/oauth-authorization-server":
                return self._handle_authorization_server_metadata(request_url)
            elif path == "/register" and method == "POST":
                return self._handle_client_registration(body)
            else:
                return self._method_not_allowed()
                
        except Exception as e:
            logger.error(f"Error handling OAuth2 request {method} {path}: {e}")
            return self._internal_server_error(str(e))
    
    def _handle_protected_resource_metadata(self, request_url: str) -> Dict[str, Any]:
        """Handle /.well-known/oauth-protected-resource endpoint."""
        try:
            from .discovery import get_protected_resource_metadata_handler
            metadata = get_protected_resource_metadata_handler(self.discovery_service, request_url)
            
            return {
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600"
                },
                "body": json.dumps(metadata, indent=2).encode('utf-8')
            }
        except Exception as e:
            logger.error(f"Error generating protected resource metadata: {e}")
            return self._internal_server_error(str(e))
    
    def _handle_authorization_server_metadata(self, request_url: str) -> Dict[str, Any]:
        """Handle /.well-known/oauth-authorization-server endpoint."""
        try:
            from .discovery import get_authorization_server_metadata_handler
            metadata = get_authorization_server_metadata_handler(self.discovery_service, request_url)
            
            return {
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "public, max-age=3600"
                },
                "body": json.dumps(metadata, indent=2).encode('utf-8')
            }
        except Exception as e:
            if "OAuth2 not enabled" in str(e):
                return self._not_found("OAuth2 not enabled")
            logger.error(f"Error generating authorization server metadata: {e}")
            return self._internal_server_error(str(e))
    
    def _handle_client_registration(self, body: Optional[bytes]) -> Dict[str, Any]:
        """Handle /register endpoint for dynamic client registration."""
        try:
            if not body:
                return self._bad_request("Request body required")
            
            registration_data = json.loads(body.decode('utf-8'))
            
            from .discovery import register_client_handler
            response = register_client_handler(self.discovery_service, registration_data)
            
            return {
                "status": 201,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store"
                },
                "body": json.dumps(response, indent=2).encode('utf-8')
            }
        except json.JSONDecodeError:
            return self._bad_request("Invalid JSON")
        except Exception as e:
            if "OAuth2 not enabled" in str(e):
                return self._not_found("OAuth2 not enabled")
            logger.error(f"Error registering client: {e}")
            return self._internal_server_error(str(e))
    
    def create_401_response(self, resource_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a 401 Unauthorized response with WWW-Authenticate header
        as required by RFC 9728 Section 5.1.
        """
        www_authenticate = self.discovery_service.create_www_authenticate_header(resource_url)
        
        return {
            "status": 401,
            "headers": {
                "Content-Type": "application/json",
                "WWW-Authenticate": www_authenticate
            },
            "body": json.dumps({
                "error": "unauthorized",
                "error_description": "Access token required"
            }, indent=2).encode('utf-8')
        }
    
    def _bad_request(self, message: str) -> Dict[str, Any]:
        """Return a 400 Bad Request response."""
        return {
            "status": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "bad_request",
                "error_description": message
            }).encode('utf-8')
        }
    
    def _not_found(self, message: str) -> Dict[str, Any]:
        """Return a 404 Not Found response."""
        return {
            "status": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "not_found",
                "error_description": message
            }).encode('utf-8')
        }
    
    def _method_not_allowed(self) -> Dict[str, Any]:
        """Return a 405 Method Not Allowed response."""
        return {
            "status": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "method_not_allowed",
                "error_description": "Method not allowed for this endpoint"
            }).encode('utf-8')
        }
    
    def _internal_server_error(self, message: str) -> Dict[str, Any]:
        """Return a 500 Internal Server Error response."""
        return {
            "status": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "internal_server_error",
                "error_description": message
            }).encode('utf-8')
        }


def create_oauth2_http_middleware(
    settings: Optional[AuthenticationSettings] = None,
    base_url: str = "http://localhost:8000"
) -> OAuth2HTTPMiddleware:
    """
    Create OAuth2 HTTP middleware with discovery service.
    
    Args:
        settings: Authentication settings (will create default if None)
        base_url: Base URL of the MCP server
        
    Returns:
        OAuth2HTTPMiddleware instance
    """
    if settings is None:
        settings = AuthenticationSettings()
    
    from .discovery import create_discovery_service
    discovery_service = create_discovery_service(settings, base_url)
    
    return OAuth2HTTPMiddleware(discovery_service)


# Helper function to integrate with various web frameworks
def setup_oauth2_discovery_routes(app, middleware: OAuth2HTTPMiddleware):
    """
    Setup OAuth2 discovery routes on a web application.
    
    This is a generic helper that can be adapted for different frameworks.
    For FastAPI, Starlette, Flask, etc.
    """
    # This would need framework-specific implementation
    # For now, it's a placeholder that shows the concept
    pass
