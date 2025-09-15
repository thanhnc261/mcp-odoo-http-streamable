# Scripts Directory

This directory contains helper scripts for development, testing, and deployment of the Odoo MCP Server.

## Scripts Overview

### `setup_dev.sh`
Development environment setup script.

**Usage:**
```bash
./scripts/setup_dev.sh
```

**Features:**
- Checks Python version (3.10+ required)
- Creates virtual environment
- Installs dependencies in development mode
- Sets up pre-commit hooks
- Creates initial `.env` configuration
- Runs initial health checks

### `dev_server.py`
Development server with hot reload functionality.

**Usage:**
```bash
python scripts/dev_server.py --transport streamable-http --port 3000
python scripts/dev_server.py --transport stdio
```

**Features:**
- Automatic server restart on code changes
- File system monitoring
- Configurable restart delay
- Support for both stdio and HTTP transports
- Debug logging enabled by default

**Options:**
- `--transport`: Transport type (stdio, streamable-http)
- `--port`: Port for HTTP transport (default: 3000)
- `--host`: Host for HTTP transport (default: 127.0.0.1)
- `--log-level`: Logging level (default: DEBUG)
- `--watch-dirs`: Directories to watch (default: src, run_server.py)
- `--restart-delay`: Delay between restarts (default: 1.0s)

### `test_runner.py`
Comprehensive test runner with various options.

**Usage:**
```bash
# Run unit tests
python scripts/test_runner.py --type unit

# Run with coverage
python scripts/test_runner.py --type unit --coverage

# Run integration tests
python scripts/test_runner.py --type integration

# Run all tests with formatting and linting
python scripts/test_runner.py --type all --format --lint --coverage

# Run specific test file
python scripts/test_runner.py --file test/test_server.py

# Run specific test function
python scripts/test_runner.py --function test_execute_method_tool
```

**Features:**
- Multiple test types (unit, integration, e2e, all)
- Code coverage reporting
- Parallel test execution
- Code formatting (black, isort)
- Linting (ruff, mypy)
- Dependency installation
- Specific file/function testing

**Options:**
- `--type`: Test type (unit, integration, e2e, all)
- `--coverage`: Enable coverage reporting
- `--verbose`: Verbose output
- `--parallel`: Number of parallel workers
- `--file`: Specific test file
- `--function`: Specific test function
- `--lint`: Run linting before tests
- `--format`: Format code before tests
- `--install-deps`: Install dependencies first

### `health_check.py`
Server health checker and diagnostics tool.

**Usage:**
```bash
# Basic health check
python scripts/health_check.py

# Check specific transport
python scripts/health_check.py --transport stdio

# Quick check (no server connectivity)
python scripts/health_check.py --quick

# JSON output
python scripts/health_check.py --output json

# Save results to file
python scripts/health_check.py --save health_report.json
```

**Features:**
- Dependency verification
- Environment variable checking
- Odoo connectivity testing
- Server health monitoring
- Comprehensive diagnostic reporting
- JSON output format
- Results persistence

**Options:**
- `--transport`: Transport type to check
- `--host`: Host for HTTP transport
- `--port`: Port for HTTP transport
- `--output`: Output format (text, json)
- `--save`: Save results to file
- `--quick`: Skip server connectivity checks

## Development Workflow

### Initial Setup
```bash
# Clone and setup
git clone <repo-url>
cd mcp-odoo-http-streamable
./scripts/setup_dev.sh
```

### Daily Development
```bash
# Activate environment
source venv/bin/activate

# Start development server with hot reload
python scripts/dev_server.py

# In another terminal - run tests
python scripts/test_runner.py --type unit --coverage

# Health check
python scripts/health_check.py
```

### Pre-commit Workflow
```bash
# Format and lint code
python scripts/test_runner.py --format --lint

# Run comprehensive tests
python scripts/test_runner.py --type all --coverage

# Health check before commit
python scripts/health_check.py --quick
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: python scripts/test_runner.py --install-deps
      
      - name: Run linting
        run: python scripts/test_runner.py --lint
      
      - name: Run tests
        run: python scripts/test_runner.py --type all --coverage
      
      - name: Health check
        run: python scripts/health_check.py --quick
```

### Docker Integration

```dockerfile
# Development image
FROM python:3.11-slim

COPY scripts/ /app/scripts/
WORKDIR /app

RUN chmod +x scripts/*.py scripts/*.sh
RUN ./scripts/setup_dev.sh

CMD ["python", "scripts/dev_server.py"]
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   chmod +x scripts/*.py scripts/*.sh
   ```

2. **Import Errors**
   ```bash
   python scripts/test_runner.py --install-deps
   ```

3. **Environment Issues**
   ```bash
   python scripts/health_check.py --quick
   ```

4. **Hot Reload Not Working**
   - Install watchdog: `pip install watchdog`
   - Check file permissions
   - Verify watch directories exist

### Script Dependencies

Some scripts require additional packages:

```bash
# For dev_server.py
pip install watchdog

# For health_check.py  
pip install requests

# For test_runner.py
pip install pytest pytest-cov pytest-asyncio

# All development dependencies
pip install -e ".[dev]"
```

## Customization

### Adding New Scripts

1. Create executable Python script with shebang:
   ```python
   #!/usr/bin/env python3
   ```

2. Add argument parsing with `argparse`

3. Include help documentation

4. Make executable: `chmod +x scripts/your_script.py`

5. Update this README

### Extending Existing Scripts

- Add new command-line options
- Extend functionality with additional checks
- Maintain backward compatibility
- Update documentation

## Best Practices

1. **Always use virtual environment**
2. **Run health checks before development**
3. **Use hot reload for active development**
4. **Run tests frequently during development**
5. **Format and lint code before commits**
6. **Use specific test targeting for faster feedback**
7. **Save health reports for troubleshooting**
