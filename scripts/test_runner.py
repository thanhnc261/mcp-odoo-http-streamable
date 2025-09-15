#!/usr/bin/env python3
"""
Test runner script for the Odoo MCP Server
Provides convenient testing options and configurations
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return the result"""
    if description:
        print(f"🔄 {description}")
    
    print(f"💻 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Test runner for Odoo MCP Server")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "e2e", "all"],
        default="unit",
        help="Type of tests to run (default: unit)"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage report"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        help="Number of parallel workers"
    )
    parser.add_argument(
        "--file",
        help="Specific test file to run"
    )
    parser.add_argument(
        "--function",
        help="Specific test function to run"
    )
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run linting before tests"
    )
    parser.add_argument(
        "--format",
        action="store_true",
        help="Format code before tests"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies before running"
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🧪 Odoo MCP Server Test Runner")
    print(f"📁 Project root: {project_root}")
    print("-" * 50)
    
    success = True
    
    # Install dependencies if requested
    if args.install_deps:
        print("📦 Installing test dependencies...")
        success &= run_command([
            sys.executable, "-m", "pip", "install", "-e", ".[dev]"
        ], "Installing dependencies")
    
    # Format code if requested
    if args.format:
        print("🎨 Formatting code...")
        success &= run_command([
            "black", "src/", "test/", "scripts/"
        ], "Running Black formatter")
        
        success &= run_command([
            "isort", "src/", "test/", "scripts/"
        ], "Running isort")
    
    # Run linting if requested
    if args.lint:
        print("🔍 Running linters...")
        success &= run_command([
            "ruff", "check", "src/", "test/", "scripts/"
        ], "Running Ruff linter")
        
        success &= run_command([
            "mypy", "src/"
        ], "Running mypy type checker")
    
    # Build pytest command
    pytest_cmd = [sys.executable, "-m", "pytest"]
    
    # Add coverage if requested
    if args.coverage:
        pytest_cmd.extend([
            "--cov=src/odoo_mcp",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    # Add verbosity
    if args.verbose:
        pytest_cmd.append("-v")
    
    # Add parallel execution
    if args.parallel:
        pytest_cmd.extend(["-n", str(args.parallel)])
    
    # Add test type markers
    if args.type == "unit":
        pytest_cmd.extend(["-m", "not integration and not e2e"])
    elif args.type == "integration":
        pytest_cmd.extend(["-m", "integration"])
    elif args.type == "e2e":
        pytest_cmd.extend(["-m", "e2e", "--run-e2e"])
    elif args.type == "all":
        pass  # Run all tests
    
    # Add specific file or function
    if args.file:
        if args.function:
            pytest_cmd.append(f"{args.file}::{args.function}")
        else:
            pytest_cmd.append(args.file)
    elif args.function:
        pytest_cmd.extend(["-k", args.function])
    
    # Run tests
    test_description = f"Running {args.type} tests"
    if args.file:
        test_description += f" for {args.file}"
    if args.function:
        test_description += f"::{args.function}"
    
    success &= run_command(pytest_cmd, test_description)
    
    # Final status
    print("-" * 50)
    if success:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
