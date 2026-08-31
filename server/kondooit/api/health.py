"""Health check endpoint."""

from __future__ import annotations

from litestar import get
from litestar.response import Response


@get("/health")
async def health() -> Response[dict[str, str]]:
    """Return server health status."""
    return Response({"status": "ok"}, status_code=200)
