"""Manages the kondooit-iroh sidecar subprocess."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SHUTDOWN_TIMEOUT = 5.0
_RESTART_DELAY = 2.0


class IrohSidecar:
    """Lifecycle manager for the kondooit-iroh binary."""

    def __init__(
        self,
        binary_path: str,
        data_dir: str,
        target_port: int,
        control_socket: str,
    ) -> None:
        self._binary_path = binary_path
        self._data_dir = data_dir
        self._target_port = target_port
        self._control_socket = control_socket
        self._process: asyncio.subprocess.Process | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        """Spawn the sidecar subprocess and begin health monitoring."""
        if self.running:
            logger.warning("Sidecar already running (pid=%s)", self._process.pid)  # type: ignore[union-attr]
            return

        self._stopping = False
        Path(self._data_dir).mkdir(parents=True, exist_ok=True)

        await self._spawn()
        self._monitor_task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        """Gracefully shut down the sidecar."""
        self._stopping = True

        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        await self._terminate()

    async def _spawn(self) -> None:
        logger.info(
            "Starting kondooit-iroh: binary=%s data_dir=%s target_port=%d",
            self._binary_path,
            self._data_dir,
            self._target_port,
        )
        self._process = await asyncio.create_subprocess_exec(
            self._binary_path,
            "--data-dir", self._data_dir,
            "--target-port", str(self._target_port),
            "--control-socket", self._control_socket,
        )
        logger.info("Sidecar started (pid=%s)", self._process.pid)

    async def _terminate(self) -> None:
        if self._process is None or self._process.returncode is not None:
            return

        logger.info("Sending SIGTERM to sidecar (pid=%s)", self._process.pid)
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=_SHUTDOWN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Sidecar did not exit in time, sending SIGKILL")
            self._process.kill()
            await self._process.wait()

        logger.info("Sidecar stopped (exit_code=%s)", self._process.returncode)
        self._process = None

    async def _monitor(self) -> None:
        """Watch the subprocess and restart on unexpected exit."""
        while not self._stopping:
            if self._process is not None:
                await self._process.wait()

            if self._stopping:
                break

            exit_code = self._process.returncode if self._process else None
            logger.warning(
                "Sidecar exited unexpectedly (exit_code=%s), restarting in %.1fs",
                exit_code,
                _RESTART_DELAY,
            )
            await asyncio.sleep(_RESTART_DELAY)

            if self._stopping:
                break

            try:
                await self._spawn()
            except Exception:
                logger.exception("Failed to restart sidecar")
