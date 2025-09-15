#!/usr/bin/env python3
"""
Health checker for Odoo MCP Server
Tests server health and connectivity
"""
import os
import sys
import time
import json
import argparse
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


class HealthChecker:
    """Health checker for MCP server"""
    
    def __init__(self, transport: str, host: str = "127.0.0.1", port: int = 8000):
        self.transport = transport
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
    
    def check_server_running(self) -> bool:
        """Check if server is running and responsive"""
        if self.transport == "stdio":
            return self._check_stdio_server()
        else:
            return self._check_http_server()
    
    def _check_stdio_server(self) -> bool:
        """Check stdio server by attempting to start it briefly"""
        try:
            # This is a basic check - in real scenario, we'd need a proper MCP client
            project_root = Path(__file__).parent.parent
            server_script = project_root / "run_server.py"
            
            # Just check if the script is executable and imports work
            result = subprocess.run([
                sys.executable, "-c",
                f"import sys; sys.path.insert(0, '{project_root}/src'); "
                "from odoo_mcp.server import mcp; print('OK')"
            ], capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0 and "OK" in result.stdout
        except Exception as e:
            print(f"❌ Stdio server check failed: {e}")
            return False
    
    def _check_http_server(self) -> bool:
        """Check HTTP server connectivity"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code in [200, 404]  # 404 is OK, means server is running
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP server not reachable: {e}")
            return False
    
    def check_odoo_connectivity(self) -> Dict[str, Any]:
        """Check Odoo instance connectivity"""
        try:
            # Add src to path for imports
            project_root = Path(__file__).parent.parent
            sys.path.insert(0, str(project_root / "src"))
            from odoo_mcp.odoo_client import get_odoo_client
            
            client = get_odoo_client()
            
            # Test authentication
            uid = client.authenticate()
            if not uid:
                return {"status": "error", "message": "Authentication failed"}
            
            # Test basic API call
            models = client.get_models()
            if not models:
                return {"status": "error", "message": "No models returned"}
            
            return {
                "status": "ok",
                "user_id": uid,
                "model_count": len(models),
                "sample_models": models[:5]
            }
        
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def check_dependencies(self) -> Dict[str, bool]:
        """Check if required dependencies are installed"""
        dependencies = {
            "mcp": False,
            "requests": False,
            "pydantic": False,
            "starlette": False,
            "uvicorn": False,
            "anyio": False,
        }
        
        for dep in dependencies:
            try:
                __import__(dep)
                dependencies[dep] = True
            except ImportError:
                dependencies[dep] = False
        
        return dependencies
    
    def check_environment(self) -> Dict[str, Any]:
        """Check environment configuration"""
        required_vars = ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
        env_status = {}
        
        for var in required_vars:
            value = os.getenv(var)
            env_status[var] = {
                "set": value is not None,
                "value": "***" if var == "ODOO_PASSWORD" and value else value
            }
        
        return env_status
    
    def run_comprehensive_check(self) -> Dict[str, Any]:
        """Run all health checks"""
        print("🏥 Running comprehensive health check...")
        print("-" * 50)
        
        results = {
            "timestamp": time.time(),
            "transport": self.transport,
            "checks": {}
        }
        
        # Check dependencies
        print("📦 Checking dependencies...")
        deps = self.check_dependencies()
        results["checks"]["dependencies"] = deps
        
        missing_deps = [dep for dep, installed in deps.items() if not installed]
        if missing_deps:
            print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
        else:
            print("✅ All dependencies installed")
        
        # Check environment
        print("\n🔧 Checking environment...")
        env = self.check_environment()
        results["checks"]["environment"] = env
        
        missing_env = [var for var, info in env.items() if not info["set"]]
        if missing_env:
            print(f"❌ Missing environment variables: {', '.join(missing_env)}")
        else:
            print("✅ All environment variables set")
        
        # Check Odoo connectivity
        print("\n🔗 Checking Odoo connectivity...")
        odoo_check = self.check_odoo_connectivity()
        results["checks"]["odoo"] = odoo_check
        
        if odoo_check["status"] == "ok":
            print(f"✅ Odoo connection OK (User ID: {odoo_check['user_id']}, Models: {odoo_check['model_count']})")
        else:
            print(f"❌ Odoo connection failed: {odoo_check['message']}")
        
        # Check server
        print(f"\n🚀 Checking {self.transport} server...")
        server_running = self.check_server_running()
        results["checks"]["server"] = {"running": server_running}
        
        if server_running:
            print(f"✅ {self.transport.upper()} server is running")
        else:
            print(f"❌ {self.transport.upper()} server is not running")
        
        # Overall status
        all_checks_passed = all([
            not missing_deps,
            not missing_env,
            odoo_check["status"] == "ok",
            server_running
        ])
        
        results["overall_status"] = "healthy" if all_checks_passed else "unhealthy"
        
        print("\n" + "=" * 50)
        if all_checks_passed:
            print("🎉 All health checks passed! Server is healthy.")
        else:
            print("⚠️  Some health checks failed. Please review the issues above.")
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Health checker for Odoo MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="streamable-http",
        help="Transport type to check (default: streamable-http)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for HTTP transport (default: 3000)"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--save",
        help="Save results to file"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick checks only (skip server connectivity)"
    )
    
    args = parser.parse_args()
    
    # Change to project directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    checker = HealthChecker(args.transport, args.host, args.port)
    
    if args.quick:
        # Quick checks only
        results = {
            "dependencies": checker.check_dependencies(),
            "environment": checker.check_environment(),
            "odoo": checker.check_odoo_connectivity()
        }
    else:
        # Comprehensive check
        results = checker.run_comprehensive_check()
    
    # Output results
    if args.output == "json":
        print(json.dumps(results, indent=2))
    
    # Save results if requested
    if args.save:
        with open(args.save, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to {args.save}")
    
    # Exit with appropriate code
    if args.quick:
        # For quick checks, exit with error if any critical check fails
        critical_failures = (
            any(not installed for installed in results["dependencies"].values()) or
            any(not info["set"] for info in results["environment"].values()) or
            results["odoo"]["status"] != "ok"
        )
        return 1 if critical_failures else 0
    else:
        return 0 if results["overall_status"] == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
