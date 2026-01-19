"""Ollama subprocess lifecycle manager."""

import asyncio
import logging
import subprocess
import signal
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"


class OllamaManager:
    """Manages Ollama subprocess lifecycle."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.ollama_url = OLLAMA_URL
        self.model_name = OLLAMA_MODEL

    async def _check_health(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def _wait_for_startup(self, max_attempts: int = 30, delay: float = 1.0) -> bool:
        """Wait for Ollama to become available."""
        logger.info(f"Waiting for Ollama to start (max {max_attempts}s)...")

        for attempt in range(max_attempts):
            if await self._check_health():
                logger.info("Ollama is ready")
                return True

            await asyncio.sleep(delay)
            logger.debug(f"Ollama startup check {attempt + 1}/{max_attempts}")

        return False

    async def _verify_model(self) -> bool:
        """Verify that required model is available."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                response.raise_for_status()

                data = response.json()
                models = data.get("models", [])

                for model in models:
                    model_name = model.get("name", "")
                    if model_name == self.model_name or model_name.startswith(f"{self.model_name}:"):
                        logger.info(f"Model {self.model_name} is available")
                        return True

                logger.error(f"Model {self.model_name} not found in Ollama")
                logger.error(f"Available models: {[m.get('name') for m in models]}")
                logger.error(f"Please run: ollama pull {self.model_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to verify model: {e}")
            return False

    async def start(self) -> None:
        """Start Ollama subprocess if not already running."""
        logger.info("Starting Ollama manager...")

        # Check if Ollama is already running
        if await self._check_health():
            logger.info("Ollama is already running")

            # Verify model
            if not await self._verify_model():
                raise RuntimeError(f"Model {self.model_name} not available. Run: ollama pull {self.model_name}")

            return

        # Start Ollama subprocess
        logger.info("Starting Ollama subprocess...")
        try:
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
            )
            logger.info(f"Ollama subprocess started with PID {self.process.pid}")
        except FileNotFoundError:
            raise RuntimeError("Ollama is not installed. Please install from https://ollama.com")
        except Exception as e:
            raise RuntimeError(f"Failed to start Ollama subprocess: {e}")

        # Wait for Ollama to become available
        if not await self._wait_for_startup():
            self.stop()
            raise RuntimeError("Ollama failed to start within timeout period")

        # Verify model
        if not await self._verify_model():
            self.stop()
            raise RuntimeError(f"Model {self.model_name} not available. Run: ollama pull {self.model_name}")

        logger.info("Ollama manager started successfully")

    def stop(self) -> None:
        """Stop Ollama subprocess if it was started by this manager."""
        if self.process:
            logger.info(f"Stopping Ollama subprocess (PID {self.process.pid})...")
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                logger.info("Ollama subprocess stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Ollama subprocess did not terminate, killing...")
                self.process.kill()
                self.process.wait()
                logger.info("Ollama subprocess killed")
            except Exception as e:
                logger.error(f"Error stopping Ollama subprocess: {e}")
            finally:
                self.process = None
