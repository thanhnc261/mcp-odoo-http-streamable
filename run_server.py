#!/usr/bin/env python
"""
Standalone script to run the Odoo MCP server 
Supports both stdio and HTTP streamable transports
Uses the same approach as in the official MCP SDK examples
"""
import sys
import os
import asyncio
import anyio
import logging
import datetime
import argparse
from pathlib import Path

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import Server
import mcp.types as types

# Import both regular and OAuth2-enabled servers
from odoo_mcp.server import mcp  # FastMCP instance from our code
try:
    from odoo_mcp.server_with_oauth2 import create_oauth2_enabled_server
    OAUTH2_AVAILABLE = True
except ImportError:
    OAUTH2_AVAILABLE = False
    logging.warning("OAuth2 components not available. Install dependencies: pip install PyJWT cryptography")


def setup_logging():
    """Set up logging to both console and file"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"mcp_server_{timestamp}.log")
    
    # Configure logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Format for both handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


def get_server_instance(args, logger):
    """
    Get the appropriate server instance based on configuration
    
    Returns:
        FastMCP server instance (with or without OAuth2)
    """
    # Check if OAuth2 should be enabled
    should_enable_oauth2 = False
    
    if args.disable_oauth2:
        logger.info("OAuth2 explicitly disabled via --disable-oauth2")
        should_enable_oauth2 = False
    elif args.enable_oauth2:
        logger.info("OAuth2 explicitly enabled via --enable-oauth2")
        should_enable_oauth2 = True
    else:
        # Auto-detect based on config file existence
        config_file = Path(args.auth_config)
        if config_file.exists():
            logger.info(f"Found OAuth2 config file: {config_file}")
            should_enable_oauth2 = True
        else:
            logger.info(f"No OAuth2 config file found at: {config_file}")
            # Check for environment variables
            if os.environ.get("MCP_AUTH_ENABLED", "").lower() == "true":
                logger.info("OAuth2 enabled via MCP_AUTH_ENABLED environment variable")
                should_enable_oauth2 = True
    
    # Create appropriate server instance
    if should_enable_oauth2 and OAUTH2_AVAILABLE:
        try:
            logger.info("Creating OAuth2-enabled server...")
            oauth2_server = create_oauth2_enabled_server(args.auth_config)
            
            # Verify OAuth2 is actually configured
            from odoo_mcp.auth import AuthenticationSettings
            settings = AuthenticationSettings(config_file=args.auth_config)
            
            if settings.is_enabled():
                logger.info(f"✅ OAuth2 authentication enabled with provider: {settings.provider}")
                if settings.provider.value == "okta":
                    logger.info(f"🏢 Okta domain: {settings.okta.domain}")
                    logger.info(f"🔑 Client ID: {settings.okta.client_id}")
                    logger.info(f"🎯 Audience: {settings.okta.audience or 'default'}")
                return oauth2_server
            else:
                logger.warning("OAuth2 config found but authentication is disabled, using regular server")
                return mcp
                
        except Exception as e:
            logger.error(f"Failed to create OAuth2-enabled server: {e}")
            logger.info("Falling back to regular server")
            return mcp
    else:
        if should_enable_oauth2 and not OAUTH2_AVAILABLE:
            logger.warning("OAuth2 requested but dependencies not available. Install: pip install PyJWT cryptography")
        logger.info("Using regular server (no OAuth2)")
        return mcp


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Run Odoo MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport type to use (default: stdio)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port to listen on for HTTP transport (default: 3000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to for HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--stateless",
        action="store_true",
        help="Run in stateless mode for HTTP transport (no session persistence)"
    )
    parser.add_argument(
        "--json-response",
        action="store_true",
        help="Use JSON responses instead of SSE streams for HTTP transport"
    )
    parser.add_argument(
        "--auth-config",
        default="auth_config.json",
        help="Path to OAuth2 authentication configuration file (default: auth_config.json)"
    )
    parser.add_argument(
        "--enable-oauth2",
        action="store_true",
        help="Enable OAuth2 authentication (requires auth_config.json or environment variables)"
    )
    parser.add_argument(
        "--disable-oauth2",
        action="store_true",
        help="Explicitly disable OAuth2 authentication even if config file exists"
    )
    return parser.parse_args()


def main() -> int:
    """
    Run the MCP server with support for both stdio and HTTP streamable transports
    """
    args = parse_args()
    logger = setup_logging()
    
    # Update logging level based on args
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        logger.info("=== ODOO MCP SERVER STARTING ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Transport: {args.transport}")
        logger.info(f"OAuth2 config file: {args.auth_config}")
        
        if args.transport == "streamable-http":
            logger.info(f"HTTP Host: {args.host}")
            logger.info(f"HTTP Port: {args.port}")
            logger.info(f"Stateless mode: {args.stateless}")
            logger.info(f"JSON response mode: {args.json_response}")
        
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith(("ODOO_", "MCP_AUTH_")):
                if "PASSWORD" in key or "SECRET" in key:
                    logger.info(f"  {key}: ***hidden***")
                else:
                    logger.info(f"  {key}: {value}")
        
        # Get the appropriate server instance (with or without OAuth2)
        server_instance = get_server_instance(args, logger)
        logger.info(f"Using server: {type(server_instance).__name__}")
        
        if args.transport == "stdio":
            # Run server in stdio mode
            async def arun_stdio():
                logger.info("Starting Odoo MCP server with stdio transport...")
                async with stdio_server() as streams:
                    logger.info("Stdio server initialized, running MCP server...")
                    await server_instance._mcp_server.run(
                        streams[0], streams[1], server_instance._mcp_server.create_initialization_options()
                    )
                    
            # Run server
            anyio.run(arun_stdio)
            
        elif args.transport == "streamable-http":
            # Run server in HTTP streamable mode using FastMCP's built-in support
            logger.info("Starting Odoo MCP server with HTTP streamable transport...")
            
            # Configure FastMCP settings for host and port
            server_instance.settings.host = args.host
            server_instance.settings.port = args.port
            
            # Configure FastMCP for the desired HTTP mode
            if args.stateless:
                logger.info("Configuring for stateless HTTP mode...")
                server_instance.settings.stateless_http = True
            
            if args.json_response:
                logger.info("Configuring for JSON response mode...")
                server_instance.settings.json_response = True
            
            # Use FastMCP's built-in run method with streamable-http transport
            server_instance.run(transport="streamable-http")
        
        logger.info("MCP server stopped normally")
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 