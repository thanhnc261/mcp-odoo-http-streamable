# Odoo MCP Server with HTTP Streamable Transport

A comprehensive MCP (Model Context Protocol) server for interacting with Odoo ERP systems, supporting both **stdio** and **HTTP streamable** transports for maximum flexibility and integration options.

## 🚀 Features

### Core Functionality
* **Dual Transport Support**: Both stdio and HTTP streamable transports
* **Comprehensive Odoo Integration**: Full access to Odoo models, records, and methods
* **Resource-based API**: Browse models, records, and search results as MCP resources
* **Tool-based API**: Execute custom methods, search employees, and query holidays
* **Real-time Streaming**: Server-Sent Events (SSE) support for HTTP transport
* **Session Management**: Stateful and stateless HTTP session options

### Transport Options
* **Stdio Transport**: Traditional stdin/stdout for direct MCP client integration
* **HTTP Streamable Transport**: RESTful HTTP API with optional SSE streaming
* **Flexible Configuration**: Stateful/stateless modes, JSON responses, CORS support

### Developer Experience
* **Hot Reload Development Server**: Automatic restart on code changes
* **Comprehensive Testing**: Unit, integration, and end-to-end tests
* **Health Monitoring**: Built-in health checks and diagnostics
* **Production Ready**: Docker support, systemd services, Kubernetes deployment

## Tools

* **execute_method**
  * Execute a custom method on an Odoo model
  * Inputs:
    * `model` (string): The model name (e.g., 'res.partner')
    * `method` (string): Method name to execute
    * `args` (optional array): Positional arguments
    * `kwargs` (optional object): Keyword arguments
  * Returns: Dictionary with the method result and success indicator

* **search_employee**
  * Search for employees by name
  * Inputs:
    * `name` (string): The name (or part of the name) to search for
    * `limit` (optional number): The maximum number of results to return (default 20)
  * Returns: Object containing success indicator, list of matching employee names and IDs, and any error message

* **search_holidays**
  * Searches for holidays within a specified date range
  * Inputs:
    * `start_date` (string): Start date in YYYY-MM-DD format
    * `end_date` (string): End date in YYYY-MM-DD format
    * `employee_id` (optional number): Optional employee ID to filter holidays
  * Returns: Object containing success indicator, list of holidays found, and any error message

## Resources

* **odoo://models**
  * Lists all available models in the Odoo system
  * Returns: JSON array of model information

* **odoo://model/{model_name}**
  * Get information about a specific model including fields
  * Example: `odoo://model/res.partner`
  * Returns: JSON object with model metadata and field definitions

* **odoo://record/{model_name}/{record_id}**
  * Get a specific record by ID
  * Example: `odoo://record/res.partner/1`
  * Returns: JSON object with record data

* **odoo://search/{model_name}/{domain}**
  * Search for records that match a domain
  * Example: `odoo://search/res.partner/[["is_company","=",true]]`
  * Returns: JSON array of matching records (limited to 10 by default)

## 📋 Quick Start

### Installation

```bash
git clone <repository-url>
cd mcp-odoo-http-streamable
pip install -e .
```

### Configuration

Set your Odoo connection details:

```bash
export ODOO_URL="https://your-odoo-instance.com"
export ODOO_DB="your_database_name"
export ODOO_USERNAME="your_username" 
export ODOO_PASSWORD="your_password"
```

### Running the Server

#### Stdio Transport (for MCP clients like Claude Desktop)
```bash
python run_server.py --transport stdio
```

#### HTTP Streamable Transport (for web applications)
```bash
# Basic HTTP server with sessions and SSE
python run_server.py --transport streamable-http --port 3000

# Stateless HTTP server (better for scaling)
python run_server.py --transport streamable-http --port 3000 --stateless

# JSON response mode (no SSE streams)
python run_server.py --transport streamable-http --port 3000 --json-response
```

## 📚 Documentation

- **[Transport Configuration](docs/transports.md)** - Detailed transport setup and options
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[Deployment Guide](docs/deployment.md)** - Production deployment instructions  
- **[Development Guide](docs/development.md)** - Contributing and extending the server

## 🛠️ Development

### Setup Development Environment

```bash
# Quick setup with script
./scripts/setup_dev.sh

# Or manual setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Development Commands

```bash
# Start development server with hot reload
python scripts/dev_server.py --transport streamable-http

# Run tests with coverage
python scripts/test_runner.py --type unit --coverage

# Health check
python scripts/health_check.py

# Format and lint code
python scripts/test_runner.py --format --lint
```

## Configuration Details

### Environment Variables

```bash
# Required Odoo Configuration
export ODOO_URL="https://your-odoo-instance.com"
export ODOO_DB="your_database"
export ODOO_USERNAME="your_username"
export ODOO_PASSWORD="your_password"

# Optional Configuration
export ODOO_API_KEY="alternative_to_password"
export MCP_LOG_LEVEL="INFO"
export MCP_HOST="127.0.0.1"
export MCP_PORT="3000"
```

### Usage with Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": [
        "-m",
        "odoo_mcp"
      ],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_DB": "your-database-name",
        "ODOO_USERNAME": "your-username",
        "ODOO_PASSWORD": "your-password-or-api-key"
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "odoo": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ODOO_URL",
        "-e",
        "ODOO_DB",
        "-e",
        "ODOO_USERNAME",
        "-e",
        "ODOO_PASSWORD",
        "mcp/odoo"
      ],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_DB": "your-database-name",
        "ODOO_USERNAME": "your-username",
        "ODOO_PASSWORD": "your-password-or-api-key"
      }
    }
  }
}
```

## Installation

### Python Package

```bash
pip install odoo-mcp
```

### Running the Server

```bash
# Using the installed package
odoo-mcp

# Using the MCP development tools
mcp dev odoo_mcp/server.py

# With additional dependencies
mcp dev odoo_mcp/server.py --with pandas --with numpy

# Mount local code for development
mcp dev odoo_mcp/server.py --with-editable .
```

## Build

Docker build:

```bash
docker build -t mcp/odoo:latest -f Dockerfile .
```

## Parameter Formatting Guidelines

When using the MCP tools for Odoo, pay attention to these parameter formatting guidelines:

1. **Domain Parameter**:
   * The following domain formats are supported:
     * List format: `[["field", "operator", value], ...]`
     * Object format: `{"conditions": [{"field": "...", "operator": "...", "value": "..."}]}`
     * JSON string of either format
   * Examples:
     * List format: `[["is_company", "=", true]]`
     * Object format: `{"conditions": [{"field": "date_order", "operator": ">=", "value": "2025-03-01"}]}`
     * Multiple conditions: `[["date_order", ">=", "2025-03-01"], ["date_order", "<=", "2025-03-31"]]`

2. **Fields Parameter**:
   * Should be an array of field names: `["name", "email", "phone"]`
   * The server will try to parse string inputs as JSON

## License

This MCP server is licensed under the MIT License.
