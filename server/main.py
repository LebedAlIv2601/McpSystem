"""Main entry point for FastAPI backend server."""

import sys

# Print immediately to verify container started (BEFORE any imports)
print("=" * 80, flush=True)
print("=== MCP BACKEND SERVER STARTING ===", flush=True)
print("=" * 80, flush=True)
print("Python version:", sys.version, flush=True)
print("Starting imports...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

import asyncio
import logging
import signal
from contextlib import asynccontextmanager

print("Step 1/5: Core imports OK", flush=True)

from fastapi import FastAPI
import uvicorn

print("Step 2/5: FastAPI imports OK", flush=True)

# Now import our modules (these will trigger config.py)
print("Step 3/5: Importing application modules (config will be checked)...", flush=True)

try:
    from logger import setup_logging
    from mcp_manager import MCPManager
    from chat_service import ChatService
    from audio_service import AudioService, set_audio_service
    from app import router, set_chat_service
    print("Step 4/5: Application modules imported successfully", flush=True)
except Exception as e:
    print(f"FATAL: Failed to import application modules: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

logger = logging.getLogger(__name__)
print("Step 5/5: Logger initialized", flush=True)

# Global state
mcp_manager: MCPManager = None
mcp_context = None
chat_service: ChatService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown of MCP connections.
    """
    global mcp_manager, mcp_context, chat_service

    logger.info("=== MCP Backend Server Starting ===")
    logger.info("Step 1/4: Initializing MCP Manager...")

    try:
        # Initialize MCP Manager with timeout
        mcp_manager = MCPManager()
        logger.info("Step 2/4: MCP Manager created, connecting to servers...")

        # Connect to MCP servers with timeout
        try:
            # Add timeout for MCP connection
            mcp_context = mcp_manager.connect()
            await asyncio.wait_for(
                mcp_context.__aenter__(),
                timeout=30.0  # 30 second timeout
            )
            logger.info("Step 3/4: MCP servers connected successfully")

            # Initialize Chat Service
            chat_service = ChatService(mcp_manager)
            chat_service.initialize()

            # Set global chat service for router
            set_chat_service(chat_service)
            logger.info(f"Step 3/4: Chat service initialized with {chat_service.get_tools_count()} tools")

        except asyncio.TimeoutError:
            logger.error("Step 3/4: MCP connection timeout after 30s - continuing without MCP tools")
            # Create minimal chat service without MCP
            chat_service = ChatService(None)
            chat_service.initialize()
            set_chat_service(chat_service)
        except Exception as mcp_error:
            logger.error(f"Step 3/4: MCP initialization failed: {mcp_error}", exc_info=True)
            logger.warning("Step 3/4: Server will run without MCP tools")
            # Create minimal chat service without MCP
            chat_service = ChatService(None)
            chat_service.initialize()
            set_chat_service(chat_service)

        # Initialize Audio Service
        logger.info("Step 4/4: Initializing Audio Service...")
        try:
            audio_service = AudioService()
            set_audio_service(audio_service)
            logger.info("Step 4/4: Audio service initialized successfully (two-stage: audio→text)")
        except Exception as audio_error:
            logger.error(f"Step 4/4: Failed to initialize Audio Service: {audio_error}", exc_info=True)
            logger.warning("Step 4/4: Server will run without voice input support")

        logger.info("=== MCP Backend Server Ready ===")
        logger.info("✓ All services initialized, server is now accepting requests")
        logger.info(f"✓ Available endpoints: /api/chat, /api/chat-voice, /api/review-pr, /health")

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
