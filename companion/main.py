#!/usr/bin/env python3
"""Kondooit Companion — launches mpv for playback and reports progress.

Usage:
    python companion/main.py --server http://localhost:8000 \
        --username admin --password secret

The companion authenticates, then polls the server for play commands.
When one arrives it launches mpv, monitors playback position via
mpv's JSON IPC protocol, and reports progress back to the server.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

POLL_INTERVAL = 2.0
PROGRESS_INTERVAL = 5.0


def login(base: str, username: str, password: str) -> str:
    r = requests.post(
        f"{base}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def poll(base: str, token: str) -> dict | None:
    r = requests.get(
        f"{base}/api/playback/poll",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def report_progress(
    base: str,
    token: str,
    cmd: dict,
    position: float,
    duration: float,
    profile_id: str | None = None,
) -> None:
    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    if profile_id:
        headers["X-Profile-Id"] = profile_id
    body = {
        "provider_key": cmd["provider_key"],
        "content_type": cmd["content_type"],
        "external_id": cmd["external_id"],
        "position_seconds": position,
        "duration_seconds": duration,
    }
    if cmd.get("series_external_id"):
        body["series_external_id"] = cmd["series_external_id"]
    if cmd.get("season_number") is not None:
        body["season_number"] = cmd["season_number"]
    if cmd.get("episode_number") is not None:
        body["episode_number"] = cmd["episode_number"]
    try:
        requests.post(
            f"{base}/api/watch-progress/report",
            json=body,
            headers=headers,
            timeout=5,
        )
    except Exception as e:
        print(f"  [progress] report failed: {e}", file=sys.stderr)


def mpv_command(sock_path: str, command: list) -> dict | None:
    """Send a JSON IPC command to mpv and return the response."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(sock_path)
        payload = json.dumps({"command": command}) + "\n"
        s.sendall(payload.encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        s.close()
        for line in data.decode().strip().split("\n"):
            try:
                parsed = json.loads(line)
                if "data" in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return None
    return None


def get_mpv_property(sock_path: str, prop: str) -> float | None:
    result = mpv_command(sock_path, ["get_property", prop])
    if result and result.get("error") == "success":
        val = result.get("data")
        if isinstance(val, (int, float)):
            return float(val)
    return None


def play_with_mpv(
    base: str,
    token: str,
    cmd: dict,
    profile_id: str | None,
) -> None:
    """Launch mpv, monitor progress, report back to server."""
    sock_dir = tempfile.mkdtemp(prefix="kondooit-mpv-")
    sock_path = os.path.join(sock_dir, "mpv.sock")

    title = cmd.get("title") or "Kondooit"
    stream_url = cmd["stream_url"]

    print(f"  Playing: {title}")
    print(f"  URL: {stream_url[:80]}...")

    mpv_args = [
        "mpv",
        f"--input-ipc-server={sock_path}",
        f"--title={title}",
        "--force-window=yes",
        stream_url,
    ]

    proc = subprocess.Popen(
        mpv_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Wait for mpv to create the socket
    for _ in range(50):
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)

    last_report = 0.0
    last_position = 0.0
    last_duration = cmd.get("duration_seconds", 0.0)

    try:
        while proc.poll() is None:
            position = get_mpv_property(sock_path, "time-pos")
            duration = get_mpv_property(sock_path, "duration")

            if position is not None:
                last_position = position
            if duration is not None and duration > 0:
                last_duration = duration

            now = time.monotonic()
            if now - last_report >= PROGRESS_INTERVAL and last_position > 0:
                report_progress(base, token, cmd, last_position, last_duration, profile_id)
                pct = (last_position / last_duration * 100) if last_duration > 0 else 0
                print(f"  [{int(last_position)}s / {int(last_duration)}s] {pct:.0f}%")
                last_report = now

            time.sleep(1.0)
    except KeyboardInterrupt:
        proc.terminate()

    # Final progress report
    if last_position > 0:
        report_progress(base, token, cmd, last_position, last_duration, profile_id)
        print(f"  Final position: {int(last_position)}s / {int(last_duration)}s")

    proc.wait()

    # Clean up socket
    try:
        os.unlink(sock_path)
        os.rmdir(sock_dir)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Kondooit Companion Player")
    parser.add_argument("--server", default="http://localhost:8000", help="Kondooit server URL")
    parser.add_argument("--username", required=True, help="Kondooit username")
    parser.add_argument("--password", required=True, help="Kondooit password")
    parser.add_argument("--profile-id", default=None, help="Profile ID for progress tracking")
    args = parser.parse_args()

    base = args.server.rstrip("/")

    print(f"Kondooit Companion — connecting to {base}")
    try:
        token = login(base, args.username, args.password)
    except Exception as e:
        print(f"Login failed: {e}", file=sys.stderr)
        sys.exit(1)
    print("Authenticated. Polling for play commands...")

    while True:
        try:
            cmd = poll(base, token)
            if cmd:
                play_with_mpv(base, token, cmd, args.profile_id)
                print("Playback finished. Resuming poll...")
            else:
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
