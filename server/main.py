"""Main entry point for FastAPI backend server."""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from logger import setup_logging
from ollama_manager import OllamaManager
from mcp_manager import MCPManager
from chat_service import ChatService
from app import router, set_chat_service

logger = logging.getLogger(__name__)

# Global state
ollama_manager: OllamaManager = None
mcp_manager: MCPManager = None
mcp_context = None
chat_service: ChatService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown of Ollama and MCP connections.
    """
    global ollama_manager, mcp_manager, mcp_context, chat_service

    logger.info("=== MCP Backend Server Starting ===")

    try:
        # Initialize and start Ollama Manager
        logger.info("Starting Ollama...")
        ollama_manager = OllamaManager()
        await ollama_manager.start()
        logger.info("Ollama started successfully")

        # Initialize MCP Manager
        mcp_manager = MCPManager()

        # Connect to MCP servers
        logger.info("Connecting to MCP servers...")
        mcp_context = mcp_manager.connect()
        await mcp_context.__aenter__()

        # Initialize Chat Service
        chat_service = ChatService(mcp_manager)
        chat_service.initialize()

        # Set global chat service for router
        set_chat_service(chat_service)

        logger.info("=== MCP Backend Server Ready ===")
        logger.info(f"Tools available: {chat_service.get_tools_count()}")

        yield

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        logger.info("=== MCP Backend Server Shutting Down ===")

        if mcp_context:
            try:
                await mcp_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP context: {e}")

        if ollama_manager:
            try:
                ollama_manager.stop()
                logger.info("Ollama stopped")
            except Exception as e:
                logger.warning(f"Error stopping Ollama: {e}")

        logger.info("=== MCP Backend Server Stopped ===")


# Create FastAPI application
app = FastAPI(
    title="MCP Backend API",
    description="Backend API for EasyPomodoro Project Consultant with MCP integration",
    version="1.0.0",
    lifespan=lifespan
)

# Include router
app.include_router(router)


def main():
    """Run the server."""
    setup_logging(level=logging.INFO)

    # Get port from environment or default
    import os
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
