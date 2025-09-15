"""
Configuration for pytest testing
"""
import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Ensure test environment
os.environ.setdefault("ODOO_URL", "http://test.odoo.com")
os.environ.setdefault("ODOO_DB", "test_db")
os.environ.setdefault("ODOO_USERNAME", "test_user")
os.environ.setdefault("ODOO_PASSWORD", "test_password")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_odoo_client():
    """Mock Odoo client for testing"""
    client = Mock()
    
    # Mock basic methods
    client.get_models.return_value = [
        {"model": "res.partner", "name": "Contact"},
        {"model": "hr.employee", "name": "Employee"},
        {"model": "hr.leave.report.calendar", "name": "Leave Report"}
    ]
    
    client.get_model_info.return_value = {
        "model": "res.partner",
        "name": "Contact",
        "description": "Partner/Contact management"
    }
    
    client.get_model_fields.return_value = {
        "id": {"type": "integer", "string": "ID", "required": True},
        "name": {"type": "char", "string": "Name", "required": True},
        "email": {"type": "char", "string": "Email", "required": False}
    }
    
    client.read_records.return_value = [
        {"id": 1, "name": "Test Partner", "email": "test@example.com"}
    ]
    
    client.search_read.return_value = [
        {"id": 1, "name": "Test Partner", "email": "test@example.com"},
        {"id": 2, "name": "Another Partner", "email": "another@example.com"}
    ]
    
    client.execute_method.return_value = [
        [1, "Test Employee"],
        [2, "Another Employee"]
    ]
    
    return client


@pytest.fixture
def mock_app_context(mock_odoo_client):
    """Mock application context with Odoo client"""
    from odoo_mcp.server import AppContext
    return AppContext(odoo=mock_odoo_client)


@pytest.fixture
async def mock_mcp_server(mock_odoo_client):
    """Create a mock MCP server for testing"""
    
    @asynccontextmanager
    async def mock_lifespan(server):
        from odoo_mcp.server import AppContext
        yield AppContext(odoo=mock_odoo_client)
    
    # Mock the FastMCP server
    with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
        from odoo_mcp.server import mcp
        # Override the lifespan context manager
        mcp._lifespan = mock_lifespan
        yield mcp


@asynccontextmanager
async def mock_session_manager():
    """Mock session manager for HTTP transport testing"""
    manager = Mock()
    manager.handle_request = AsyncMock()
    manager.run = asynccontextmanager(lambda: AsyncMock().__aenter__())
    yield manager
