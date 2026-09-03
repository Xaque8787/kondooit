"""Stream handle proxy endpoint (ADR-0013).

Serves bytes for an opaque stream handle. Clients never see upstream
URLs or credentials — they request GET /streams/{stream_id} and the
server proxies from the upstream provider.
"""

from __future__ import annotations

import logging

import httpx
from litestar import Controller, Request, get
from litestar.response import Stream
from litestar.exceptions import NotFoundException

from kondooit.application.stream_store import StreamHandleStore

logger = logging.getLogger(__name__)


class StreamController(Controller):
    path = "/streams"

    @get("/{stream_id:str}")
    async def stream_proxy(
        self,
        stream_id: str,
        request: Request,
        stream_store: StreamHandleStore,
    ) -> Stream:
        handle = stream_store.get(stream_id)
        if handle is None:
            raise NotFoundException("Stream not found or expired")

        upstream_headers: dict[str, str] = dict(handle.upstream_headers)
        range_header = request.headers.get("range")
        if range_header:
            upstream_headers["Range"] = range_header

        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=300.0),
            follow_redirects=True,
            auth=handle.upstream_auth,
        )

        try:
            upstream_resp = await client.send(
                client.build_request("GET", handle.upstream_url, headers=upstream_headers),
                stream=True,
            )
        except Exception as e:
            await client.aclose()
            logger.error("Stream proxy upstream failed for %s: %s", stream_id, e)
            from litestar.exceptions import ServiceUnavailableException
            raise ServiceUnavailableException("Failed to connect to upstream provider")

        if upstream_resp.status_code not in (200, 206):
            body = (await upstream_resp.aread())[:500]
            await upstream_resp.aclose()
            await client.aclose()
            logger.warning("Stream proxy upstream returned %d for %s — body: %s",
                           upstream_resp.status_code, stream_id, body)
            from litestar.exceptions import ServiceUnavailableException
            raise ServiceUnavailableException("Upstream provider returned an error")

        response_headers: dict[str, str] = {
            "Accept-Ranges": "bytes",
        }
        if handle.filename:
            response_headers["Content-Disposition"] = f'inline; filename="{handle.filename}"'
        content_length = upstream_resp.headers.get("content-length")
        if content_length:
            response_headers["Content-Length"] = content_length
        content_range = upstream_resp.headers.get("content-range")
        if content_range:
            response_headers["Content-Range"] = content_range

        async def stream_generator():
            try:
                async for chunk in upstream_resp.aiter_bytes(chunk_size=131072):
                    yield chunk
            finally:
                await upstream_resp.aclose()
                await client.aclose()

        return Stream(
            stream_generator(),
            status_code=upstream_resp.status_code,
            media_type=handle.content_type,
            headers=response_headers,
        )
