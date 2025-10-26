#!/usr/bin/env python3
"""
Startup script for Grafana IRM Webhook Server
Provides an easy way to start the FastAPI server with proper configuration
"""

import os
import sys
from pathlib import Path

import uvicorn


def main():
    """Start the FastAPI server with configuration"""

    # Load environment variables from .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv()

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    log_level = "debug" if debug else "info"

    print(f"🚀 Starting Grafana IRM Webhook Server")
    print(f"📍 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🐛 Debug: {debug}")
    print(f"📊 Log Level: {log_level}")
    print(f"📚 API Docs: http://{host}:{port}/docs")
    print(f"📖 ReDoc: http://{host}:{port}/redoc")
    print("-" * 50)

    # Start the server
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
