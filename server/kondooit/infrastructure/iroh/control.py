"""Unix socket client for the kondooit-iroh control interface."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 5.0


class IrohControlClient:
    """Sends JSON-line commands to the sidecar's Unix domain socket."""

    def __init__(self, socket_path: str) -> None:
        self._socket_path = socket_path

    async def status(self) -> dict[str, Any]:
        """Return sidecar status: online, endpoint_id, relay_connected."""
        return await self._command({"cmd": "status"})

    async def generate_ticket(self) -> str:
        """Generate and return an endpoint ticket string."""
        resp = await self._command({"cmd": "ticket"})
        return resp["ticket"]

    async def shutdown(self) -> None:
        """Ask the sidecar to shut down gracefully."""
        try:
            await self._command({"cmd": "shutdown"})
        except (ConnectionError, asyncio.TimeoutError):
            # Expected — the process may exit before replying
            pass

    async def _command(
        self,
        payload: dict[str, Any],
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(self._socket_path),
            timeout=timeout,
        )
        try:
            line = json.dumps(payload) + "\n"
            writer.write(line.encode())
            await writer.drain()

            raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not raw:
                raise ConnectionError("Sidecar closed connection without response")

            return json.loads(raw)
        finally:
            writer.close()
            await writer.wait_closed()
