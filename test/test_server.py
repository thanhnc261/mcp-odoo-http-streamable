"""
Test basic server functionality and tools
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock


class TestOdooMCPServer:
    """Test cases for the Odoo MCP Server"""
    
    def test_server_initialization(self, mock_mcp_server):
        """Test that the server initializes properly"""
        assert mock_mcp_server is not None
        assert hasattr(mock_mcp_server, '_mcp_server')
    
    @pytest.mark.asyncio
    async def test_get_models_resource(self, mock_odoo_client):
        """Test the get_models resource"""
        with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
            from odoo_mcp.server import get_models
            result = get_models()
            
            # Should return JSON string
            assert isinstance(result, str)
            models = json.loads(result)
            assert isinstance(models, list)
            assert len(models) > 0
            assert models[0]["model"] == "res.partner"
    
    @pytest.mark.asyncio
    async def test_get_model_info_resource(self, mock_odoo_client):
        """Test the get_model_info resource"""
        with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
            from odoo_mcp.server import get_model_info
            result = get_model_info("res.partner")
            
            # Should return JSON string
            assert isinstance(result, str)
            model_info = json.loads(result)
            assert model_info["model"] == "res.partner"
            assert "fields" in model_info
    
    @pytest.mark.asyncio
    async def test_get_record_resource(self, mock_odoo_client):
        """Test the get_record resource"""
        with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
            from odoo_mcp.server import get_record
            result = get_record("res.partner", "1")
            
            # Should return JSON string
            assert isinstance(result, str)
            record = json.loads(result)
            assert record["id"] == 1
            assert record["name"] == "Test Partner"
    
    @pytest.mark.asyncio
    async def test_search_records_resource(self, mock_odoo_client):
        """Test the search_records resource"""
        with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
            from odoo_mcp.server import search_records_resource
            domain = '[["name", "ilike", "test"]]'
            result = search_records_resource("res.partner", domain)
            
            # Should return JSON string
            assert isinstance(result, str)
            records = json.loads(result)
            assert isinstance(records, list)
            assert len(records) > 0
    
    @pytest.mark.asyncio
    async def test_execute_method_tool(self, mock_app_context):
        """Test the execute_method tool"""
        from odoo_mcp.server import execute_method
        
        # Mock context
        mock_context = Mock()
        mock_context.request_context.lifespan_context = mock_app_context
        
        result = execute_method(
            mock_context,
            "hr.employee",
            "name_search",
            [],
            {"name": "test", "limit": 10}
        )
        
        assert result["success"] is True
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_search_employee_tool(self, mock_app_context):
        """Test the search_employee tool"""
        from odoo_mcp.server import search_employee
        
        # Mock context
        mock_context = Mock()
        mock_context.request_context.lifespan_context = mock_app_context
        
        result = search_employee(mock_context, "test", 20)
        
        assert result.success is True
        assert result.result is not None
        assert len(result.result) > 0
        assert result.result[0].name == "Test Employee"
    
    @pytest.mark.asyncio
    async def test_search_holidays_tool(self, mock_app_context):
        """Test the search_holidays tool"""
        from odoo_mcp.server import search_holidays
        
        # Mock context and setup holidays data
        mock_context = Mock()
        mock_context.request_context.lifespan_context = mock_app_context
        
        # Mock holidays data
        mock_app_context.odoo.search_read.return_value = [
            {
                "display_name": "Test Holiday",
                "start_datetime": "2024-01-01 00:00:00",
                "stop_datetime": "2024-01-02 00:00:00", 
                "employee_id": [1, "Test Employee"],
                "name": "Test Leave",
                "state": "validate"
            }
        ]
        
        result = search_holidays(mock_context, "2024-01-01", "2024-01-31")
        
        assert result.success is True
        assert result.result is not None
        assert len(result.result) > 0
        assert result.result[0].name == "Test Leave"
    
    @pytest.mark.asyncio
    async def test_search_holidays_invalid_date(self, mock_app_context):
        """Test the search_holidays tool with invalid date format"""
        from odoo_mcp.server import search_holidays
        
        # Mock context
        mock_context = Mock()
        mock_context.request_context.lifespan_context = mock_app_context
        
        result = search_holidays(mock_context, "invalid-date", "2024-01-31")
        
        assert result.success is False
        assert "Invalid start_date format" in result.error
    
    @pytest.mark.asyncio
    async def test_domain_condition_conversion(self):
        """Test DomainCondition to_tuple conversion"""
        from odoo_mcp.server import DomainCondition
        
        condition = DomainCondition(
            field="name",
            operator="ilike", 
            value="test"
        )
        
        result = condition.to_tuple()
        assert result == ["name", "ilike", "test"]
    
    @pytest.mark.asyncio
    async def test_search_domain_conversion(self):
        """Test SearchDomain to_domain_list conversion"""
        from odoo_mcp.server import SearchDomain, DomainCondition
        
        domain = SearchDomain(conditions=[
            DomainCondition(field="name", operator="ilike", value="test"),
            DomainCondition(field="active", operator="=", value=True)
        ])
        
        result = domain.to_domain_list()
        expected = [["name", "ilike", "test"], ["active", "=", True]]
        assert result == expected


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_get_record_not_found(self, mock_odoo_client):
        """Test get_record when record is not found"""
        mock_odoo_client.read_records.return_value = []
        
        with patch('odoo_mcp.server.get_odoo_client', return_value=mock_odoo_client):
            from odoo_mcp.server import get_record
            result = get_record("res.partner", "999")
            
            # Should return error JSON
            assert isinstance(result, str)
            error_result = json.loads(result)
            assert "error" in error_result
            assert "Record not found" in error_result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_method_exception(self, mock_app_context):
        """Test execute_method when exception occurs"""
        from odoo_mcp.server import execute_method
        
        # Mock context with exception
        mock_context = Mock()
        mock_context.request_context.lifespan_context = mock_app_context
        mock_app_context.odoo.execute_method.side_effect = Exception("Test error")
        
        result = execute_method(
            mock_context,
            "hr.employee",
            "name_search",
            [],
            {"name": "test"}
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]
