"""HLS remux/transcode endpoint with smart codec selection.

Probes upstream media with ffprobe to detect codecs and duration,
then picks the lightest FFmpeg pipeline the client can play:
  1. Remux (copy both video+audio) — fastest, near-zero CPU
  2. Remux video + transcode audio — fast, minimal CPU
  3. Full transcode — slow, for incompatible video codecs (HEVC on Chrome)

Exposes real duration via an info endpoint so the player can show
accurate progress regardless of how much has been transcoded.

Supports seeking past the transcoded frontier by killing FFmpeg
and restarting with -ss at the requested position.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.response import Response

from kondooit.application.stream_store import StreamHandleStore, StreamHandle

logger = logging.getLogger(__name__)

HLS_SEGMENT_DIR = Path(tempfile.gettempdir()) / "kondooit_hls"
SEGMENT_DURATION = 6
STALE_SESSION_SECONDS = 3600
MIN_SEGMENTS_BEFORE_SERVE = 2

# Codecs browsers can natively decode in MPEG-TS via hls.js / MSE
BROWSER_VIDEO_CODECS = {"h264", "avc", "avc1"}
BROWSER_AUDIO_CODECS = {"aac", "mp3", "mp4a", "opus"}


@dataclass
class ProbeResult:
    video_codec: str = ""
    audio_codec: str = ""
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    video_bit_depth: int = 8


async def ffprobe_url(url: str, header_str: str = "") -> ProbeResult | None:
    """Run ffprobe on a URL to detect codecs and duration."""

    cmd = [
        "ffprobe",
        "-hide_banner",
        "-loglevel", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-select_streams", "v:0",
    ]
    if header_str:
        cmd.extend(["-headers", header_str])
    cmd.append(url)

    # Also probe audio in a second pass (ffprobe -select_streams limits output)
    cmd_audio = [
        "ffprobe",
        "-hide_banner",
        "-loglevel", "error",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a:0",
    ]
    if header_str:
        cmd_audio.extend(["-headers", header_str])
    cmd_audio.append(url)

    try:
        proc_v, proc_a = await asyncio.gather(
            asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            ),
            asyncio.create_subprocess_exec(
                *cmd_audio, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            ),
        )

        (stdout_v, stderr_v), (stdout_a, _stderr_a) = await asyncio.gather(
            asyncio.wait_for(proc_v.communicate(), timeout=30),
            asyncio.wait_for(proc_a.communicate(), timeout=30),
        )
    except (asyncio.TimeoutError, FileNotFoundError) as e:
        logger.error("ffprobe failed: %s", e)
        return None

    result = ProbeResult()

    try:
        data_v = json.loads(stdout_v)
        if data_v.get("streams"):
            vs = data_v["streams"][0]
            result.video_codec = (vs.get("codec_name") or "").lower()
            result.width = int(vs.get("width") or 0)
            result.height = int(vs.get("height") or 0)
            bits = vs.get("bits_per_raw_sample") or vs.get("bits_per_component")
            if bits:
                result.video_bit_depth = int(bits)

        fmt = data_v.get("format", {})
        dur = fmt.get("duration")
        if dur:
            result.duration_seconds = float(dur)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("ffprobe video parse error: %s", e)

    try:
        data_a = json.loads(stdout_a)
        if data_a.get("streams"):
            result.audio_codec = (data_a["streams"][0].get("codec_name") or "").lower()
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # If duration not in format, try video stream duration
    if result.duration_seconds <= 0:
        try:
            data_v = json.loads(stdout_v)
            for s in data_v.get("streams", []):
                d = s.get("duration")
                if d and float(d) > 0:
                    result.duration_seconds = float(d)
                    break
        except Exception:
            pass

    logger.info(
        "Probe result: video=%s audio=%s duration=%.1fs %dx%d %dbit",
        result.video_codec, result.audio_codec, result.duration_seconds,
        result.width, result.height, result.video_bit_depth,
    )
    return result


def decide_codecs(
    probe: ProbeResult,
    client_video_codecs: set[str] | None = None,
    client_audio_codecs: set[str] | None = None,
) -> tuple[list[str], list[str], str]:
    """Decide FFmpeg video and audio codec flags.

    Returns (video_flags, audio_flags, decision_reason).
    video_flags: e.g. ["-c:v", "copy"] or ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"]
    audio_flags: e.g. ["-c:a", "copy"] or ["-c:a", "aac", "-b:a", "192k"]
    """
    supported_video = client_video_codecs or BROWSER_VIDEO_CODECS
    supported_audio = client_audio_codecs or BROWSER_AUDIO_CODECS

    # Normalize codec names
    vc = probe.video_codec.lower()
    ac = probe.audio_codec.lower()

    # Map common names
    vc_normalized = vc
    if vc in ("h264", "avc", "avc1"):
        vc_normalized = "h264"
    elif vc in ("hevc", "h265", "hev1", "hvc1"):
        vc_normalized = "hevc"
    elif vc in ("av1", "av01"):
        vc_normalized = "av1"

    ac_normalized = ac
    if ac in ("aac", "mp4a"):
        ac_normalized = "aac"
    elif ac in ("eac3", "ec-3", "ec3"):
        ac_normalized = "eac3"
    elif ac in ("ac3", "ac-3"):
        ac_normalized = "ac3"
    elif ac in ("truehd", "mlp"):
        ac_normalized = "truehd"
    elif ac in ("dts", "dca"):
        ac_normalized = "dts"
    elif ac in ("flac",):
        ac_normalized = "flac"
    elif ac in ("opus",):
        ac_normalized = "opus"

    # Video decision
    can_copy_video = vc_normalized in supported_video
    # 10-bit H.264 High 10 often fails in browsers
    if vc_normalized == "h264" and probe.video_bit_depth > 8:
        can_copy_video = False

    # No audio stream at all
    if not ac:
        video_flags = ["-c:v", "copy"] if can_copy_video else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"]
        reason = f"remux video (copy {vc}), no audio" if can_copy_video else f"transcode video ({vc}->h264), no audio"
        return video_flags, [], reason

    # Audio decision
    can_copy_audio = ac_normalized in supported_audio

    if can_copy_video and can_copy_audio:
        reason = f"remux (copy {vc}+{ac})"
        return ["-c:v", "copy"], ["-c:a", "copy"], reason
    elif can_copy_video:
        reason = f"remux video (copy {vc}), transcode audio ({ac}->aac)"
        return ["-c:v", "copy"], ["-c:a", "aac", "-b:a", "192k"], reason
    elif can_copy_audio:
        reason = f"transcode video ({vc}->h264), copy audio ({ac})"
        return (
            ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"],
            ["-c:a", "copy"],
            reason,
        )
    else:
        reason = f"full transcode ({vc}->h264, {ac}->aac)"
        return (
            ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"],
            ["-c:a", "aac", "-b:a", "192k"],
            reason,
        )


def _build_input_url(handle: StreamHandle) -> str:
    return handle.upstream_url


def _build_auth_headers(handle: StreamHandle) -> str:
    """Build FFmpeg -headers string including auth and User-Agent."""
    import base64
    parts: list[str] = []
    parts.append("User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n")
    if handle.upstream_auth:
        user, pw = handle.upstream_auth
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        parts.append(f"Authorization: Basic {token}\r\n")
    for k, v in handle.upstream_headers.items():
        parts.append(f"{k}: {v}\r\n")
    return "".join(parts)


class HlsSession:
    """Tracks a running FFmpeg process for one stream."""

    def __init__(
        self,
        stream_id: str,
        handle: StreamHandle,
        output_dir: Path,
        probe: ProbeResult | None = None,
        client_video_codecs: set[str] | None = None,
        client_audio_codecs: set[str] | None = None,
    ) -> None:
        self.stream_id = stream_id
        self.handle = handle
        self.output_dir = output_dir
        self.probe = probe
        self.client_video_codecs = client_video_codecs
        self.client_audio_codecs = client_audio_codecs
        self.process: asyncio.subprocess.Process | None = None
        self.started_at = time.monotonic()
        self.last_access = time.monotonic()
        self.start_offset: float = 0.0
        self._started = False
        self._failed = False
        self._finished = False
        self._error_message = ""
        self._decision_reason = ""
        self._stderr_task: asyncio.Task | None = None

    @property
    def duration_seconds(self) -> float:
        return self.probe.duration_seconds if self.probe else 0.0

    async def start(self, seek_seconds: float = 0.0) -> None:
        self.start_offset = seek_seconds
        self.output_dir.mkdir(parents=True, exist_ok=True)

        playlist_path = self.output_dir / "stream.m3u8"
        segment_pattern = self.output_dir / "seg_%05d.m4s"

        input_headers = _build_auth_headers(self.handle)
        cmd_input = _build_input_url(self.handle)

        # Decide codecs
        if self.probe:
            video_flags, audio_flags, reason = decide_codecs(
                self.probe, self.client_video_codecs, self.client_audio_codecs,
            )
        else:
            video_flags = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"]
            audio_flags = ["-c:a", "aac", "-b:a", "192k"]
            reason = "full transcode (no probe data)"

        self._decision_reason = reason

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y"]

        if input_headers:
            cmd.extend(["-headers", input_headers])

        cmd.extend([
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
        ])

        if seek_seconds > 0:
            cmd.extend(["-ss", f"{seek_seconds:.3f}"])

        cmd.extend(["-i", cmd_input, "-map", "0:v:0"])
        if audio_flags:
            cmd.extend(["-map", "0:a:0"])
        cmd.extend(video_flags)
        cmd.extend(audio_flags)

        # Force keyframes at segment boundaries when transcoding video
        if video_flags[1] != "copy":
            cmd.extend(["-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_DURATION})"])

        start_number = int(seek_seconds / SEGMENT_DURATION) if seek_seconds > 0 else 0

        cmd.extend([
            "-f", "hls",
            "-hls_time", str(SEGMENT_DURATION),
            "-hls_list_size", "0",
            "-hls_playlist_type", "event",
            "-hls_flags", "independent_segments+append_list",
            "-hls_segment_type", "fmp4",
            "-hls_fmp4_init_filename", "init.mp4",
            "-start_number", str(start_number),
            "-hls_segment_filename", str(segment_pattern),
            str(playlist_path),
        ])

        logger.info(
            "Starting HLS for stream %s: %s (seek=%.1fs)",
            self.stream_id, reason, seek_seconds,
        )
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
        return len(list(self.output_dir.glob("seg_*.m4s")))

    def max_seekable_seconds(self) -> float:
        """Approximate furthest point we have segments for."""
        count = self.segment_count()
        return self.start_offset + (count * SEGMENT_DURATION)

    async def stop(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()

    def cleanup_files(self) -> None:
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def touch(self) -> None:
        self.last_access = time.monotonic()


MAX_STREAM_FAILURES = 3


class HlsSessionManager:
    """Manages active HLS sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, HlsSession] = {}
        self._probes: dict[str, ProbeResult] = {}
        self._failure_counts: dict[str, int] = {}

    def is_permanently_failed(self, stream_id: str) -> bool:
        return self._failure_counts.get(stream_id, 0) >= MAX_STREAM_FAILURES

    async def get_or_create(
        self,
        stream_id: str,
        handle: StreamHandle,
        client_video_codecs: set[str] | None = None,
        client_audio_codecs: set[str] | None = None,
    ) -> HlsSession | None:
        if self.is_permanently_failed(stream_id):
            return None

        if stream_id in self._sessions:
            session = self._sessions[stream_id]
            if session.failed:
                self._failure_counts[stream_id] = self._failure_counts.get(stream_id, 0) + 1
                if self._failure_counts[stream_id] >= MAX_STREAM_FAILURES:
                    logger.error("Stream %s permanently failed after %d attempts", stream_id, self._failure_counts[stream_id])
                    await self.remove(stream_id)
                    return None
                await self.remove(stream_id)
            else:
                session.touch()
                return session

        await self._sweep()

        # Probe once per stream and cache
        probe = self._probes.get(stream_id)
        if probe is None:
            input_url = _build_input_url(handle)
            auth_headers = _build_auth_headers(handle)
            probe = await ffprobe_url(input_url, auth_headers)
            if probe:
                self._probes[stream_id] = probe

        # If probe returned empty codecs, the upstream URL is unreachable
        if probe and not probe.video_codec and not probe.audio_codec:
            logger.error("Probe returned no codecs for %s — upstream URL likely unreachable", stream_id)
            self._failure_counts[stream_id] = MAX_STREAM_FAILURES
            return None

        session_hash = hashlib.sha256(stream_id.encode()).hexdigest()[:12]
        output_dir = HLS_SEGMENT_DIR / session_hash
        session = HlsSession(
            stream_id, handle, output_dir,
            probe=probe,
            client_video_codecs=client_video_codecs,
            client_audio_codecs=client_audio_codecs,
        )
        await session.start()
        self._sessions[stream_id] = session
        return session

    async def seek(
        self,
        stream_id: str,
        handle: StreamHandle,
        seek_seconds: float,
        client_video_codecs: set[str] | None = None,
        client_audio_codecs: set[str] | None = None,
    ) -> HlsSession:
        """Kill current FFmpeg and restart at the requested position."""
        old = self._sessions.pop(stream_id, None)
        probe = self._probes.get(stream_id)
        if old:
            await old.stop()
            old.cleanup_files()
            if not probe:
                probe = old.probe

        session_hash = hashlib.sha256(stream_id.encode()).hexdigest()[:12]
        output_dir = HLS_SEGMENT_DIR / session_hash
        session = HlsSession(
            stream_id, handle, output_dir,
            probe=probe,
            client_video_codecs=client_video_codecs,
            client_audio_codecs=client_audio_codecs,
        )
        await session.start(seek_seconds=seek_seconds)
        self._sessions[stream_id] = session
        return session

    def get(self, stream_id: str) -> HlsSession | None:
        session = self._sessions.get(stream_id)
        if session:
            session.touch()
        return session

    def get_probe(self, stream_id: str) -> ProbeResult | None:
        return self._probes.get(stream_id)

    async def remove(self, stream_id: str, clear_failure_count: bool = False) -> None:
        session = self._sessions.pop(stream_id, None)
        self._probes.pop(stream_id, None)
        if clear_failure_count:
            self._failure_counts.pop(stream_id, None)
        if session:
            await session.stop()
            session.cleanup_files()

    async def _sweep(self) -> None:
        now = time.monotonic()
        stale = [
            sid for sid, s in self._sessions.items()
            if now - s.last_access > STALE_SESSION_SECONDS
        ]
        for sid in stale:
            await self.remove(sid)


def _parse_codec_set(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    codecs = {c.strip().lower() for c in raw.split(",") if c.strip()}
    return codecs if codecs else None


class HlsController(Controller):
    path = "/hls"

    @get("/{stream_id:str}/info")
    async def get_info(
        self,
        stream_id: str,
        stream_store: StreamHandleStore,
        hls_manager: HlsSessionManager,
    ) -> Response:
        """Return probe info and session status.

        The player calls this before requesting the playlist to get
        the real duration and codec decision.
        """
        handle = stream_store.get(stream_id)
        if handle is None:
            raise NotFoundException("Stream not found or expired")

        # Check permanent failure first
        if hls_manager.is_permanently_failed(stream_id):
            return Response(
                content={"stream_id": stream_id, "failed": True, "error": "Stream source is unreachable"},
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # Probe if not already cached
        probe = hls_manager.get_probe(stream_id)
        if probe is None:
            input_url = _build_input_url(handle)
            probe = await ffprobe_url(input_url, _build_auth_headers(handle))
            if probe:
                hls_manager._probes[stream_id] = probe

        # Detect unreachable upstream
        probe_failed = probe is None or (not probe.video_codec and not probe.audio_codec)

        session = hls_manager.get(stream_id)

        info: dict = {
            "stream_id": stream_id,
            "duration_seconds": probe.duration_seconds if probe else 0,
            "video_codec": probe.video_codec if probe else "",
            "audio_codec": probe.audio_codec if probe else "",
            "width": probe.width if probe else 0,
            "height": probe.height if probe else 0,
            "probe_failed": probe_failed,
        }
        if probe_failed:
            info["error"] = "Could not reach the source — the link may have expired"
        if session:
            info["decision"] = session._decision_reason
            info["transcoded_seconds"] = session.max_seekable_seconds()
            info["is_running"] = session.is_running
            info["failed"] = session.failed
        return Response(
            content=info,
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    @get("/{stream_id:str}/master.m3u8")
    async def get_playlist(
        self,
        stream_id: str,
        stream_store: StreamHandleStore,
        hls_manager: HlsSessionManager,
        vc: str | None = None,
        ac: str | None = None,
    ) -> Response:
        """Serve the HLS playlist.

        Query params:
          vc - comma-separated video codecs the client supports (e.g. "h264,av1")
          ac - comma-separated audio codecs the client supports (e.g. "aac,mp3,opus")
        """
        handle = stream_store.get(stream_id)
        if handle is None:
            raise NotFoundException("Stream not found or expired")

        client_vc = _parse_codec_set(vc)
        client_ac = _parse_codec_set(ac)

        session = await hls_manager.get_or_create(
            stream_id, handle,
            client_video_codecs=client_vc,
            client_audio_codecs=client_ac,
        )

        if session is None:
            return Response(
                content="Stream permanently failed after multiple attempts",
                status_code=410,
                media_type="text/plain",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        if session.failed:
            return Response(
                content=f"HLS failed: {session._error_message}",
                status_code=500,
                media_type="text/plain",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        playlist_path = session.output_dir / "stream.m3u8"

        retries = 0
        while retries < 150:
            if session.failed:
                return Response(
                    content=f"HLS failed: {session._error_message}",
                    status_code=500,
                    media_type="text/plain",
                    headers={"Access-Control-Allow-Origin": "*"},
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
                headers={"Retry-After": "2", "Access-Control-Allow-Origin": "*"},
            )

        content = playlist_path.read_text()

        return Response(
            content=content,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Cache-Control": "no-cache, no-store",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @get("/{stream_id:str}/seek")
    async def seek_stream(
        self,
        stream_id: str,
        stream_store: StreamHandleStore,
        hls_manager: HlsSessionManager,
        t: float = 0.0,
        vc: str | None = None,
        ac: str | None = None,
    ) -> Response:
        """Seek to a position. Kills FFmpeg and restarts at the new offset.

        Query params:
          t  - target time in seconds
          vc - client video codecs
          ac - client audio codecs
        """
        handle = stream_store.get(stream_id)
        if handle is None:
            raise NotFoundException("Stream not found or expired")

        client_vc = _parse_codec_set(vc)
        client_ac = _parse_codec_set(ac)

        session = await hls_manager.seek(
            stream_id, handle, seek_seconds=t,
            client_video_codecs=client_vc,
            client_audio_codecs=client_ac,
        )

        if session.failed:
            return Response(
                content={"error": session._error_message},
                status_code=500,
            )

        return Response(
            content={
                "seeked_to": t,
                "start_offset": session.start_offset,
            },
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*"},
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

        retries = 0
        while not segment_path.exists() and retries < 25:
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
        await hls_manager.remove(stream_id, clear_failure_count=True)
        return Response(content={"stopped": True}, status_code=200)
