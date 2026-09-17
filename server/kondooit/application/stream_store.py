"""In-memory stream handle store (ADR-0013).

Issues opaque, short-lived stream handles that map to upstream
provider details. Clients never see upstream URLs or credentials;
they receive a handle and request bytes via their current transport.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StreamHandle:
    stream_id: str
    provider_key: str
    upstream_url: str
    upstream_headers: dict[str, str] = field(default_factory=dict)
    upstream_auth: tuple[str, str] | None = None
    filename: str = ""
    content_type: str = "application/octet-stream"
    created_at: float = 0.0
    expires_at: float = 0.0
    allow_remux: bool = True
    allow_transcode: bool = False


DEFAULT_TTL_SECONDS = 4 * 3600  # 4 hours


class StreamHandleStore:
    """Thread-safe (single-event-loop) in-memory store for stream handles."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._handles: dict[str, StreamHandle] = {}
        self._ttl = ttl_seconds

    def create(
        self,
        *,
        provider_key: str,
        upstream_url: str,
        upstream_headers: dict[str, str] | None = None,
        upstream_auth: tuple[str, str] | None = None,
        filename: str = "",
        content_type: str = "application/octet-stream",
        allow_remux: bool = True,
        allow_transcode: bool = False,
    ) -> str:
        self._sweep()
        stream_id = f"kd_{secrets.token_urlsafe(16)}"
        now = time.monotonic()
        self._handles[stream_id] = StreamHandle(
            stream_id=stream_id,
            provider_key=provider_key,
            upstream_url=upstream_url,
            upstream_headers=upstream_headers or {},
            upstream_auth=upstream_auth,
            filename=filename,
            content_type=content_type,
            created_at=now,
            expires_at=now + self._ttl,
            allow_remux=allow_remux,
            allow_transcode=allow_transcode,
        )
        return stream_id

    def get(self, stream_id: str) -> StreamHandle | None:
        handle = self._handles.get(stream_id)
        if handle is None:
            return None
        if time.monotonic() > handle.expires_at:
            del self._handles[stream_id]
            return None
        return handle

    def remove(self, stream_id: str) -> None:
        self._handles.pop(stream_id, None)

    def _sweep(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._handles.items() if now > v.expires_at]
        for k in expired:
            del self._handles[k]
