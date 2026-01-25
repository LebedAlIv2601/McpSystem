"""Main entry point for EasyPomodoro Project Consultant Telegram bot."""

import asyncio
import logging
import signal
import sys

from logger import setup_logging
from bot import TelegramBot
from ollama_manager import OllamaManager
from analytics_manager import AnalyticsManager

logger = logging.getLogger(__name__)


class Application:
    """Main application orchestrator."""

    def __init__(self):
        self.ollama_manager: OllamaManager = None
        self.analytics_manager: AnalyticsManager = None
        self.bot: TelegramBot = None
        self.shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Initialize and start all components."""
        logger.info("Application startup initiated")

        # Start Ollama manager
        self.ollama_manager = OllamaManager()
        await self.ollama_manager.start()

        # Start Analytics MCP manager
        self.analytics_manager = AnalyticsManager()
        await self.analytics_manager.start()

        # Start Telegram bot
        self.bot = TelegramBot(analytics_manager=self.analytics_manager)
        await self.bot.run()

        logger.info("Application startup completed")

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        logger.info("Application shutdown initiated")

        if self.bot:
            await self.bot.stop()

        if self.analytics_manager:
            await self.analytics_manager.stop()

        if self.ollama_manager:
            self.ollama_manager.stop()

        logger.info("Application shutdown completed")

    async def run(self) -> None:
        """Run the application until shutdown signal."""
        try:
            await self.startup()
            await self.shutdown_event.wait()
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    def signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown")
        self.shutdown_event.set()


async def main() -> None:
    """Application entry point."""
    setup_logging(level=logging.INFO)

    logger.info("=== EasyPomodoro Project Consultant Bot Starting ===")

    app = Application()

    signal.signal(signal.SIGINT, lambda s, f: app.signal_handler(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: app.signal_handler(s, f))

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=== EasyPomodoro Project Consultant Bot Stopped ===")


if __name__ == "__main__":
    asyncio.run(main())
