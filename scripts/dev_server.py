#!/usr/bin/env python3
"""
Development server runner with hot reload
Automatically restarts the server when code changes are detected
"""
import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ServerHandler(FileSystemEventHandler):
    """Handler for file system events that restarts the server"""
    
    def __init__(self, command, restart_delay=1.0):
        self.command = command
        self.restart_delay = restart_delay
        self.process = None
        self.last_restart = 0
        self.start_server()
    
    def start_server(self):
        """Start the server process"""
        if self.process:
            self.stop_server()
        
        print(f"🚀 Starting server: {' '.join(self.command)}")
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # Print server output in real-time
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    print(line.rstrip())
                    
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
    
    def stop_server(self):
        """Stop the server process"""
        if self.process:
            print("🛑 Stopping server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("⚠️  Force killing server...")
                self.process.kill()
            self.process = None
    
    def restart_server(self):
        """Restart the server with debouncing"""
        current_time = time.time()
        if current_time - self.last_restart < self.restart_delay:
            return
        
        self.last_restart = current_time
        print("🔄 Restarting server due to file changes...")
        self.start_server()
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        # Only restart for Python files and configuration files
        if event.src_path.endswith(('.py', '.toml', '.json', '.yaml', '.yml')):
            print(f"📝 File changed: {event.src_path}")
            self.restart_server()


def main():
    parser = argparse.ArgumentParser(description="Development server with hot reload")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="streamable-http",
        help="Transport type (default: streamable-http)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port for HTTP transport (default: 3000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="DEBUG",
        help="Log level (default: DEBUG)"
    )
    parser.add_argument(
        "--watch-dirs",
        nargs="+",
        default=["src", "run_server.py"],
        help="Directories/files to watch for changes"
    )
    parser.add_argument(
        "--restart-delay",
        type=float,
        default=1.0,
        help="Delay between restarts in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    # Build server command
    project_root = Path(__file__).parent.parent
    server_script = project_root / "run_server.py"
    
    command = [
        sys.executable,
        str(server_script),
        "--transport", args.transport,
        "--log-level", args.log_level
    ]
    
    if args.transport == "streamable-http":
        command.extend([
            "--port", str(args.port),
            "--host", args.host
        ])
    
    print("🔧 Development server with hot reload")
    print(f"📁 Project root: {project_root}")
    print(f"🎯 Watching: {args.watch_dirs}")
    print(f"⚡ Restart delay: {args.restart_delay}s")
    print("-" * 50)
    
    # Set up file system observer
    event_handler = ServerHandler(command, args.restart_delay)
    observer = Observer()
    
    # Watch specified directories
    for watch_path in args.watch_dirs:
        full_path = project_root / watch_path
        if full_path.exists():
            observer.schedule(
                event_handler,
                str(full_path),
                recursive=full_path.is_dir()
            )
            print(f"👁️  Watching: {full_path}")
        else:
            print(f"⚠️  Warning: {full_path} does not exist")
    
    try:
        observer.start()
        print("\n✅ Hot reload active. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        observer.stop()
        event_handler.stop_server()
    
    observer.join()
    print("👋 Development server stopped.")


if __name__ == "__main__":
    try:
        import watchdog
    except ImportError:
        print("❌ watchdog package required for hot reload")
        print("Install with: pip install watchdog")
        sys.exit(1)
    
    main()
