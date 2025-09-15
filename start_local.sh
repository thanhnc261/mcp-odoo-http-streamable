P#!/bin/bash

# Local development startup script for Odoo MCP Server
# This script sets up the environment and starts the server with appropriate settings

set -e  # Exit on any error

echo "🚀 Starting Odoo MCP Server for Local Development"
echo "================================================="

# Set default values
TRANSPORT=${TRANSPORT:-"streamable-http"}
HOST=${HOST:-"127.0.0.1"}
PORT=${PORT:-3000}
AUTH_MODE=${AUTH_MODE:-"auto"}  # auto, enabled, disabled
CONFIG_FILE=${CONFIG_FILE:-"auth_config.json"}

echo "📋 Configuration:"
echo "  Transport: $TRANSPORT"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Auth Mode: $AUTH_MODE"
echo "  Config File: $CONFIG_FILE"

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "📦 Activating virtual environment from parent directory..."
    source ../venv/bin/activate
else
    echo "⚠️  No virtual environment found. Make sure dependencies are installed."
fi

# Check for required environment variables
echo ""
echo "🔍 Checking Odoo configuration..."
if [ -z "$ODOO_URL" ]; then
    echo "⚠️  ODOO_URL not set. Using default: http://localhost:8069"
    export ODOO_URL="http://localhost:8069"
fi

if [ -z "$ODOO_DB" ]; then
    echo "⚠️  ODOO_DB not set. Using default: odoo"
    export ODOO_DB="odoo"
fi

if [ -z "$ODOO_USERNAME" ]; then
    echo "⚠️  ODOO_USERNAME not set. Using default: admin"
    export ODOO_USERNAME="admin"
fi

if [ -z "$ODOO_PASSWORD" ]; then
    echo "❌ ODOO_PASSWORD not set. Please set it:"
    echo "   export ODOO_PASSWORD='your-password'"
    exit 1
fi

echo "✅ Odoo URL: $ODOO_URL"
echo "✅ Odoo DB: $ODOO_DB"
echo "✅ Odoo Username: $ODOO_USERNAME"
echo "✅ Odoo Password: ***set***"

# Check OAuth2 configuration
echo ""
echo "🔐 Checking OAuth2 configuration..."
if [ "$AUTH_MODE" = "disabled" ]; then
    echo "🔓 OAuth2 explicitly disabled"
    AUTH_ARGS="--disable-oauth2"
elif [ "$AUTH_MODE" = "enabled" ]; then
    echo "🔐 OAuth2 explicitly enabled"
    AUTH_ARGS="--enable-oauth2 --auth-config $CONFIG_FILE"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "❌ Auth config file not found: $CONFIG_FILE"
        echo "📝 Creating example config file..."
        
        cat > "$CONFIG_FILE" << EOF
{
  "enabled": false,
  "provider": "okta",
  "okta": {
    "domain": "your-domain.okta.com",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "audience": "api://your-api"
  }
}
EOF
        echo "✅ Created $CONFIG_FILE with example configuration"
        echo "📝 Please update $CONFIG_FILE with your Okta settings and set enabled: true"
        echo "💡 Or run with AUTH_MODE=disabled to skip OAuth2"
        exit 1
    fi
else
    echo "🔍 Auto-detecting OAuth2 configuration..."
    AUTH_ARGS="--auth-config $CONFIG_FILE"
    
    if [ -f "$CONFIG_FILE" ]; then
        echo "✅ Found auth config file: $CONFIG_FILE"
    else
        echo "📝 No auth config file found, OAuth2 will be disabled"
    fi
fi

# Install dependencies if needed
echo ""
echo "📦 Checking dependencies..."
python -c "import mcp" 2>/dev/null || {
    echo "❌ MCP package not found. Installing dependencies..."
    pip install -e .
}

python -c "import jwt, cryptography" 2>/dev/null || {
    echo "⚠️  OAuth2 dependencies not found. Installing..."
    pip install PyJWT cryptography
}

# Build the command
CMD="python run_server.py --transport $TRANSPORT --host $HOST --port $PORT $AUTH_ARGS"

echo ""
echo "🎯 Starting server..."
echo "Command: $CMD"
echo ""

if [ "$TRANSPORT" = "streamable-http" ]; then
    echo "🌐 Server will be available at: http://$HOST:$PORT"
    echo "📖 API docs (if available): http://$HOST:$PORT/docs"
    echo ""
fi

echo "💡 Use Ctrl+C to stop the server"
echo "================================================="
echo ""

# Run the server
exec $CMD
