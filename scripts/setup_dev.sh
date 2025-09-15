#!/usr/bin/env bash
"""
Setup script for Odoo MCP Server development environment
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_step() {
    echo -e "${BLUE}🔧 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Python 3.10+ is available
check_python() {
    print_step "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            print_error "Python 3.10+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 not found"
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_step "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists, removing..."
        rm -rf venv
    fi
    
    $PYTHON_CMD -m venv venv
    print_success "Virtual environment created"
}

# Activate virtual environment
activate_venv() {
    print_step "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
}

# Install dependencies
install_dependencies() {
    print_step "Installing dependencies..."
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install the package in development mode
    pip install -e ".[dev]"
    
    # Install additional development tools
    pip install \
        watchdog \
        ipdb \
        jupyter \
        notebook
    
    print_success "Dependencies installed"
}

# Setup pre-commit hooks
setup_precommit() {
    print_step "Setting up pre-commit hooks..."
    
    if command -v pre-commit &> /dev/null; then
        pre-commit install
        print_success "Pre-commit hooks installed"
    else
        print_warning "pre-commit not found, skipping hooks setup"
    fi
}

# Create environment file
create_env_file() {
    print_step "Creating environment configuration..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Odoo Configuration
ODOO_URL=http://localhost:8069
ODOO_DB=test_db
ODOO_USERNAME=admin
ODOO_PASSWORD=admin

# MCP Server Configuration
MCP_LOG_LEVEL=DEBUG
MCP_HOST=127.0.0.1
MCP_PORT=3000
EOF
        print_success "Environment file created (.env)"
        print_warning "Please update .env with your actual Odoo configuration"
    else
        print_success "Environment file already exists"
    fi
}

# Setup development configuration
setup_dev_config() {
    print_step "Setting up development configuration..."
    
    # Create logs directory
    mkdir -p logs
    
    # Create test configuration
    if [ ! -f "pytest.ini" ]; then
        print_warning "pytest.ini not found, basic testing may not work properly"
    fi
    
    print_success "Development configuration complete"
}

# Run initial tests
run_tests() {
    print_step "Running initial tests..."
    
    if python -m pytest test/ -v --tb=short; then
        print_success "Tests passed"
    else
        print_warning "Some tests failed - this is normal for initial setup"
    fi
}

# Check Odoo connectivity
check_odoo() {
    print_step "Checking Odoo connectivity..."
    
    if python scripts/health_check.py --quick --output json > /dev/null 2>&1; then
        print_success "Odoo connectivity check passed"
    else
        print_warning "Odoo connectivity check failed - please verify your configuration"
    fi
}

# Main setup function
main() {
    echo "🚀 Odoo MCP Server Development Environment Setup"
    echo "=============================================="
    
    # Get project directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_DIR"
    
    echo "📁 Project directory: $PROJECT_DIR"
    echo ""
    
    # Run setup steps
    check_python
    create_venv
    activate_venv
    install_dependencies
    setup_precommit
    create_env_file
    setup_dev_config
    
    echo ""
    echo "🎉 Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Activate the virtual environment: source venv/bin/activate"
    echo "2. Update .env with your Odoo configuration"
    echo "3. Run health check: python scripts/health_check.py"
    echo "4. Start development server: python scripts/dev_server.py"
    echo "5. Run tests: python scripts/test_runner.py"
    echo ""
    echo "Development commands:"
    echo "  Start server:     python run_server.py --transport streamable-http"
    echo "  Run tests:        python scripts/test_runner.py"
    echo "  Health check:     python scripts/health_check.py"
    echo "  Dev server:       python scripts/dev_server.py"
    echo ""
}

# Run setup if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
