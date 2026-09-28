"""Remote access API endpoints for iroh-based connectivity."""

from __future__ import annotations

import base64
import json
import logging

from litestar import Controller, get, post
from litestar.exceptions import HTTPException
from pydantic import BaseModel

from kondooit.api.guards import jwt_guard, get_current_user
from kondooit.config import Settings
from kondooit.infrastructure.iroh.control import IrohControlClient
from kondooit.infrastructure.iroh.sidecar import IrohSidecar

logger = logging.getLogger(__name__)


class RemoteAccessStatusResponse(BaseModel):
    enabled: bool
    online: bool
    endpoint_id: str | None
    relay_connected: bool


class ConnectionUrlResponse(BaseModel):
    url: str


class RemoteAccessController(Controller):
    path = "/remote-access"
    tags = ["Remote Access"]
    guards = [jwt_guard]

    @get(
        "/status",
        summary="Get remote access status",
        dependencies={"current_user": get_current_user},
    )
    async def status(
        self,
        current_user: dict,
        iroh_sidecar: IrohSidecar,
        iroh_control: IrohControlClient,
        settings: Settings,
    ) -> RemoteAccessStatusResponse:
        if not settings.iroh_enabled or not iroh_sidecar.running:
            return RemoteAccessStatusResponse(
                enabled=settings.iroh_enabled,
                online=False,
                endpoint_id=None,
                relay_connected=False,
            )

        try:
            info = await iroh_control.status()
        except Exception:
            logger.exception("Failed to query sidecar status")
            return RemoteAccessStatusResponse(
                enabled=True,
                online=False,
                endpoint_id=None,
                relay_connected=False,
            )

        return RemoteAccessStatusResponse(
            enabled=True,
            online=info.get("online", False),
            endpoint_id=info.get("endpoint_id"),
            relay_connected=info.get("relay_connected", False),
        )

    @post(
        "/enable",
        summary="Enable remote access and start sidecar",
        dependencies={"current_user": get_current_user},
    )
    async def enable(
        self,
        current_user: dict,
        iroh_sidecar: IrohSidecar,
        settings: Settings,
    ) -> RemoteAccessStatusResponse:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        settings.iroh_enabled = True
        await iroh_sidecar.start()
        return RemoteAccessStatusResponse(
            enabled=True,
            online=iroh_sidecar.running,
            endpoint_id=None,
            relay_connected=False,
        )

    @post(
        "/disable",
        summary="Disable remote access and stop sidecar",
        dependencies={"current_user": get_current_user},
    )
    async def disable(
        self,
        current_user: dict,
        iroh_sidecar: IrohSidecar,
        settings: Settings,
    ) -> RemoteAccessStatusResponse:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        settings.iroh_enabled = False
        await iroh_sidecar.stop()
        return RemoteAccessStatusResponse(
            enabled=False,
            online=False,
            endpoint_id=None,
            relay_connected=False,
        )

    @get(
        "/connection-url",
        summary="Get the connection URL for the browser runtime",
        dependencies={"current_user": get_current_user},
    )
    async def connection_url(
        self,
        current_user: dict,
        iroh_sidecar: IrohSidecar,
        iroh_control: IrohControlClient,
        settings: Settings,
    ) -> ConnectionUrlResponse:
        if not settings.iroh_enabled or not iroh_sidecar.running:
            raise HTTPException(status_code=409, detail="Remote access is not enabled")

        try:
            info = await iroh_control.status()
        except Exception:
            logger.exception("Failed to query sidecar for connection URL")
            raise HTTPException(status_code=503, detail="Sidecar unavailable")

        endpoint_id = info.get("endpoint_id")
        if not endpoint_id:
            raise HTTPException(status_code=503, detail="Endpoint not ready")

        payload = json.dumps({"v": 1, "endpoint_id": endpoint_id}).encode()
        fragment = base64.urlsafe_b64encode(payload).decode().rstrip("=")

        runtime_base = settings.runtime_base_url.rstrip("/") + "/"
        url = f"{runtime_base}#{fragment}"

        return ConnectionUrlResponse(url=url)
