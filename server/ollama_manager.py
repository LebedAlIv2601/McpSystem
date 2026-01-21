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
        self.model_ready = False
        self._pull_task: Optional[asyncio.Task] = None

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

    async def _pull_model(self) -> bool:
        """Pull model from Ollama registry."""
        logger.info(f"Pulling model {self.model_name} (this may take 5-10 minutes on first run)...")
        logger.info("Note: App will start serving requests while model downloads in background")

        try:
            async with httpx.AsyncClient(timeout=900.0) as client:
                # Start the pull request
                async with client.stream(
                    'POST',
                    f"{self.ollama_url}/api/pull",
                    json={"name": self.model_name}
                ) as response:
                    response.raise_for_status()

                    last_status = ""
                    completed_layers = set()

                    # Stream progress updates
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                import json
                                data = json.loads(line)
                                status = data.get("status", "")
                                digest = data.get("digest", "")

                                # Only log new statuses to avoid spam
                                if status != last_status:
                                    if "pulling" in status.lower():
                                        logger.info(f"Model pull: {status}")
                                    elif "downloading" in status.lower():
                                        completed = data.get("completed", 0)
                                        total = data.get("total", 0)
                                        if total > 0:
                                            percent = (completed / total) * 100
                                            logger.info(f"Downloading: {percent:.1f}% ({completed}/{total} bytes)")
                                    elif status == "verifying sha256 digest":
                                        logger.info("Verifying downloaded model...")
                                    elif status == "writing manifest":
                                        logger.info("Writing model manifest...")
                                    elif status == "success":
                                        logger.info(f"Model {self.model_name} pulled successfully!")
                                        return True

                                    last_status = status

                                # Track completed layers
                                if digest and status == "success":
                                    if digest not in completed_layers:
                                        completed_layers.add(digest)
                                        logger.info(f"Layer completed: {digest[:12]}... ({len(completed_layers)} layers done)")

                            except json.JSONDecodeError:
                                continue

                    logger.info(f"Model pull completed")
                    return True

        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False

    async def _background_pull(self) -> None:
        """Pull model in background."""
        try:
            logger.info(f"Starting background pull of model {self.model_name}")
            success = await self._pull_model()
            if success:
                self.model_ready = True
                logger.info(f"Background model pull completed - model is ready")
            else:
                logger.error(f"Background model pull failed")
        except Exception as e:
            logger.error(f"Background pull error: {e}")

    async def _verify_model(self, auto_pull: bool = True, background: bool = False) -> bool:
        """Verify that required model is available, optionally pull it if missing."""
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
                        self.model_ready = True
                        return True

                # Model not found
                logger.warning(f"Model {self.model_name} not found in Ollama")
                logger.info(f"Available models: {[m.get('name') for m in models]}")

                # Auto-pull if enabled
                if auto_pull:
                    if background:
                        # Start background pull task
                        logger.info(f"Starting background pull of model {self.model_name}")
                        self._pull_task = asyncio.create_task(self._background_pull())
                        return True  # Don't block startup
                    else:
                        # Blocking pull
                        logger.info(f"Attempting to pull model {self.model_name}...")
                        if await self._pull_model():
                            self.model_ready = True
                            return True
                        else:
                            logger.error(f"Failed to pull model {self.model_name}")
                            return False
                else:
                    logger.error(f"Please run: ollama pull {self.model_name}")
                    return False

        except Exception as e:
            logger.error(f"Failed to verify model: {e}")
            return False

    def is_model_ready(self) -> bool:
        """Check if model is ready for use."""
        return self.model_ready

    async def start(self, background_pull: bool = True) -> None:
        """
        Start Ollama subprocess if not already running.

        Args:
            background_pull: If True, pull missing models in background without blocking startup.
                            If False, block until model is available (legacy behavior).
        """
        logger.info("Starting Ollama manager...")

        # Check if Ollama is already running
        if await self._check_health():
            logger.info("Ollama is already running")

            # Verify model (non-blocking if background_pull=True)
            await self._verify_model(background=background_pull)

            if not self.model_ready and not background_pull:
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

        # Verify model (non-blocking if background_pull=True)
        await self._verify_model(background=background_pull)

        if not self.model_ready and not background_pull:
            self.stop()
            raise RuntimeError(f"Model {self.model_name} not available. Run: ollama pull {self.model_name}")

        if self.model_ready:
            logger.info("Ollama manager started successfully with model ready")
        else:
            logger.info("Ollama manager started successfully (model downloading in background)")

    def stop(self) -> None:
        """Stop Ollama subprocess if it was started by this manager."""
        # Cancel background pull task if running
        if self._pull_task and not self._pull_task.done():
            logger.info("Cancelling background model pull task...")
            self._pull_task.cancel()
            self._pull_task = None

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
