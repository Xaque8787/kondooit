"""HLS remux endpoint — streaming event mode with MPEG-TS segments.

Serves growing-playlist HLS for browser playback. FFmpeg writes MPEG-TS
segments (.ts) and an event playlist that grows as segments appear. The
client starts playback as soon as the first few segments are ready.

This is the "proxy + remux" tier from ADR-0014.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import tempfile
import time
from pathlib import Path

from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.response import Response

from kondooit.application.stream_store import StreamHandleStore, StreamHandle

logger = logging.getLogger(__name__)

HLS_SEGMENT_DIR = Path(tempfile.gettempdir()) / "kondooit_hls"
SEGMENT_DURATION = 6
STALE_SESSION_SECONDS = 3600
MIN_SEGMENTS_BEFORE_SERVE = 3


class HlsSession:
    """Tracks a running FFmpeg remux process for one stream."""

    def __init__(self, stream_id: str, handle: StreamHandle, output_dir: Path) -> None:
        self.stream_id = stream_id
        self.handle = handle
        self.output_dir = output_dir
        self.process: asyncio.subprocess.Process | None = None
        self.started_at = time.monotonic()
        self.last_access = time.monotonic()
        self._started = False
        self._failed = False
        self._finished = False
        self._error_message = ""
        self._stderr_task: asyncio.Task | None = None

    async def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        playlist_path = self.output_dir / "stream.m3u8"
        segment_pattern = self.output_dir / "seg_%05d.ts"

        input_headers = ""
        for k, v in self.handle.upstream_headers.items():
            input_headers += f"{k}: {v}\r\n"

        if self.handle.upstream_auth:
            user, pw = self.handle.upstream_auth
            auth_url = self.handle.upstream_url
            scheme_end = auth_url.find("://")
            if scheme_end >= 0:
                auth_url = auth_url[:scheme_end + 3] + f"{user}:{pw}@" + auth_url[scheme_end + 3:]
                cmd_input = auth_url
            else:
                cmd_input = self.handle.upstream_url
        else:
            cmd_input = self.handle.upstream_url

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-y",
        ]

        if input_headers:
            cmd.extend(["-headers", input_headers])

        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", cmd_input,
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-f", "hls",
            "-hls_time", str(SEGMENT_DURATION),
            "-hls_list_size", "0",
            "-hls_playlist_type", "event",
            "-hls_flags", "independent_segments+append_list",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", str(segment_pattern),
            str(playlist_path),
        ])

        logger.info("Starting HLS remux for stream %s", self.stream_id)
        logger.info("Upstream URL (first 80 chars): %s", cmd_input[:80])

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._started = True
            self._stderr_task = asyncio.create_task(self._read_stderr())
        except FileNotFoundError:
            self._failed = True
            self._error_message = "FFmpeg not found on the server"
            logger.error("FFmpeg binary not found")
        except Exception as e:
            self._failed = True
            self._error_message = str(e)
            logger.error("Failed to start FFmpeg: %s", e)

    async def _read_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return
        lines: list[str] = []
        try:
            while True:
                line_bytes = await self.process.stderr.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                lines.append(line)
                logger.info("FFmpeg [%s]: %s", self.stream_id[:12], line)
        except Exception:
            pass

        returncode = await self.process.wait()
        if returncode != 0:
            self._failed = True
            tail = "\n".join(lines[-10:]) if lines else "(no output)"
            self._error_message = f"FFmpeg exited with code {returncode}: {tail}"
            logger.error("FFmpeg failed for %s (exit %d): %s", self.stream_id, returncode, tail)
        else:
            self._finished = True
            elapsed = time.monotonic() - self.started_at
            logger.info("FFmpeg finished for %s in %.1fs", self.stream_id, elapsed)

    @property
    def is_running(self) -> bool:
        if not self._started or self.process is None:
            return False
        return self.process.returncode is None

    @property
    def failed(self) -> bool:
        return self._failed

    def segment_count(self) -> int:
        if not self.output_dir.exists():
            return 0
        return len(list(self.output_dir.glob("seg_*.ts")))

    async def stop(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def touch(self) -> None:
        self.last_access = time.monotonic()


class HlsSessionManager:
    """Manages active HLS remux sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, HlsSession] = {}

    async def get_or_create(self, stream_id: str, handle: StreamHandle) -> HlsSession:
        if stream_id in self._sessions:
            session = self._sessions[stream_id]
            if session.failed:
                await self.remove(stream_id)
            else:
                session.touch()
                return session

        await self._sweep()

        session_hash = hashlib.sha256(stream_id.encode()).hexdigest()[:12]
        output_dir = HLS_SEGMENT_DIR / session_hash
        session = HlsSession(stream_id, handle, output_dir)
        await session.start()
        self._sessions[stream_id] = session
        return session

    def get(self, stream_id: str) -> HlsSession | None:
        session = self._sessions.get(stream_id)
        if session:
            session.touch()
        return session

    async def remove(self, stream_id: str) -> None:
        session = self._sessions.pop(stream_id, None)
        if session:
            await session.stop()

    async def _sweep(self) -> None:
        now = time.monotonic()
        stale = [
            sid for sid, s in self._sessions.items()
            if now - s.last_access > STALE_SESSION_SECONDS
        ]
        for sid in stale:
            await self.remove(sid)


class HlsController(Controller):
    path = "/hls"

    @get("/{stream_id:str}/master.m3u8")
    async def get_playlist(
        self,
        stream_id: str,
        stream_store: StreamHandleStore,
        hls_manager: HlsSessionManager,
    ) -> Response:
        handle = stream_store.get(stream_id)
        if handle is None:
            raise NotFoundException("Stream not found or expired")

        session = await hls_manager.get_or_create(stream_id, handle)

        if session.failed:
            return Response(
                content=f"HLS remux failed: {session._error_message}",
                status_code=500,
                media_type="text/plain",
            )

        playlist_path = session.output_dir / "stream.m3u8"

        # Wait for enough segments before first serve
        retries = 0
        while retries < 150:
            if session.failed:
                return Response(
                    content=f"HLS remux failed: {session._error_message}",
                    status_code=500,
                    media_type="text/plain",
                )
            if playlist_path.exists() and session.segment_count() >= MIN_SEGMENTS_BEFORE_SERVE:
                break
            if session._finished and playlist_path.exists():
                break
            await asyncio.sleep(0.2)
            retries += 1

        if not playlist_path.exists():
            return Response(
                content="Playlist not ready yet",
                status_code=503,
                media_type="text/plain",
                headers={"Retry-After": "2"},
            )

        content = playlist_path.read_text()

        # For event playlists, hls.js needs to know it can start from beginning
        # If FFmpeg finished, the playlist has #EXT-X-ENDLIST already
        return Response(
            content=content,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Cache-Control": "no-cache, no-store",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @get("/{stream_id:str}/{filename:str}")
    async def get_segment(
        self,
        stream_id: str,
        filename: str,
        hls_manager: HlsSessionManager,
    ) -> Response:
        session = hls_manager.get(stream_id)
        if session is None:
            raise NotFoundException("HLS session not found")

        safe_name = Path(filename).name
        if "/" in filename or ".." in filename:
            raise NotFoundException("Invalid segment path")

        segment_path = session.output_dir / safe_name

        # Brief wait for segment to appear (FFmpeg may still be writing)
        retries = 0
        while not segment_path.exists() and retries < 15:
            await asyncio.sleep(0.2)
            retries += 1

        if not segment_path.exists():
            raise NotFoundException(f"Segment {safe_name} not found")

        content = segment_path.read_bytes()

        if safe_name.endswith(".ts"):
            media_type = "video/mp2t"
        elif safe_name.endswith(".m4s"):
            media_type = "video/iso.segment"
        elif safe_name.endswith(".mp4"):
            media_type = "video/mp4"
        else:
            media_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Cache-Control": "max-age=3600",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @get("/{stream_id:str}/stop")
    async def stop_session(
        self,
        stream_id: str,
        hls_manager: HlsSessionManager,
    ) -> Response:
        await hls_manager.remove(stream_id)
        return Response(content={"stopped": True}, status_code=200)
