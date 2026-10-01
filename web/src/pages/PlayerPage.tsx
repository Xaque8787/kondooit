import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Hls from "hls.js";
import { api, apiFetch } from "../api";
import { detectCodecs } from "../codecs";
import { isConnected } from "../tunnel";
import { TunnelHlsLoader } from "../TunnelHlsLoader";

const detected = detectCodecs();
const clientCodecs = { vc: detected.video.join(","), ac: detected.audio.join(",") };

interface StreamInfo {
  duration_seconds: number;
  video_codec: string;
  audio_codec: string;
  width: number;
  height: number;
  decision?: string;
  transcoded_seconds?: number;
  is_running?: boolean;
  probe_failed?: boolean;
  error?: string;
  failed?: boolean;
}

function formatTime(s: number): string {
  if (!s || !isFinite(s) || s < 0) return "0:00";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function describeMethod(decision: string): { method: string; reason: string } {
  if (!decision) return { method: "Unknown", reason: "" };
  if (decision.startsWith("remux (copy")) {
    return { method: "Remux", reason: "Video and audio copied directly -- no processing needed." };
  }
  if (decision.startsWith("remux video")) {
    const match = decision.match(/transcode audio \((.+?)->(.+?)\)/);
    if (match) {
      return {
        method: "Partial Transcode",
        reason: `Video is copied directly. Audio converted from ${match[1].toUpperCase()} to ${match[2].toUpperCase()} because your browser cannot play ${match[1].toUpperCase()}.`,
      };
    }
    return { method: "Partial Transcode", reason: "Video copied, audio being converted." };
  }
  if (decision.startsWith("transcode video") && decision.includes("copy audio")) {
    const match = decision.match(/transcode video \((.+?)->(.+?)\)/);
    if (match) {
      return {
        method: "Transcode",
        reason: `Video converted from ${match[1].toUpperCase()} to ${match[2].toUpperCase()} because your browser cannot play ${match[1].toUpperCase()}. Audio is copied directly.`,
      };
    }
    return { method: "Transcode", reason: "Video being converted, audio copied." };
  }
  if (decision.startsWith("full transcode")) {
    const match = decision.match(/\((.+?)->(.+?), (.+?)->(.+?)\)/);
    if (match) {
      return {
        method: "Full Transcode",
        reason: `Video converted from ${match[1].toUpperCase()} to ${match[2].toUpperCase()} and audio from ${match[3].toUpperCase()} to ${match[4].toUpperCase()} because your browser cannot play either format natively.`,
      };
    }
    return { method: "Full Transcode", reason: "Both video and audio are being converted for your browser." };
  }
  return { method: decision, reason: "" };
}

export function PlayerPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const seekBarRef = useRef<HTMLDivElement>(null);

  const autoPlaySession = params.get("aps") || "";
  const [activeStreamId, setActiveStreamId] = useState(params.get("stream") || "");
  const streamId = activeStreamId;
  const title = params.get("title") || "Untitled";
  const providerKey = params.get("provider") || "";
  const contentType = params.get("type") || "movie";
  const externalId = parseInt(params.get("eid") || "0", 10);
  const seriesExternalId = params.get("series_eid") ? parseInt(params.get("series_eid")!, 10) : undefined;
  const seasonNumber = params.get("season") ? parseInt(params.get("season")!, 10) : undefined;
  const episodeNumber = params.get("episode") ? parseInt(params.get("episode")!, 10) : undefined;

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState("Preparing stream...");
  const [showControls, setShowControls] = useState(true);
  const [isSeeking, setIsSeeking] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPaused, setIsPaused] = useState(true);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const realDuration = streamInfo?.duration_seconds || 0;
  const videoDuration = videoRef.current?.duration || 0;
  const effectiveDuration = realDuration > 0 ? realDuration : videoDuration;

  const codecParams = `vc=${encodeURIComponent(clientCodecs.vc)}&ac=${encodeURIComponent(clientCodecs.ac)}`;

  const reportProgress = useCallback(() => {
    const video = videoRef.current;
    if (!video || !providerKey || !externalId) return;
    const pos = Math.floor(video.currentTime);
    const dur = Math.floor(realDuration || video.duration) || 0;
    if (pos <= 0 || dur <= 0) return;
    api.beaconProgress({
      provider_key: providerKey,
      content_type: contentType,
      external_id: externalId,
      position_seconds: pos,
      duration_seconds: dur,
      series_external_id: seriesExternalId,
      season_number: seasonNumber,
      episode_number: episodeNumber,
    });
  }, [providerKey, contentType, externalId, seriesExternalId, seasonNumber, episodeNumber, realDuration]);

  const tryNextAutoPlaySource = useCallback(async () => {
    if (!autoPlaySession || !streamId) return;
    setLoading(true);
    setLoadingMessage("Trying next source...");
    setError("");
    try {
      const res = await api.autoPlayNext(autoPlaySession, streamId);
      if (res.success && res.stream_id) {
        setActiveStreamId(res.stream_id);
      } else {
        setError("All sources failed. Please go back and try manually.");
        setLoading(false);
      }
    } catch {
      setError("All sources failed. Please go back and try manually.");
      setLoading(false);
    }
  }, [autoPlaySession, streamId]);

  const createHls = useCallback((hlsUrl: string, videoEl: HTMLVideoElement, onReady?: () => void) => {
    const hlsConfig: Partial<ConstructorParameters<typeof Hls>[0]> = {
      maxBufferLength: 30,
      maxMaxBufferLength: 120,
      maxBufferHole: 0.5,
      startLevel: -1,
      manifestLoadingRetryDelay: 2000,
      manifestLoadingMaxRetry: 5,
      levelLoadingRetryDelay: 2000,
      levelLoadingMaxRetry: 6,
      fragLoadingRetryDelay: 1000,
      fragLoadingMaxRetry: 6,
      debug: false,
    };
    if (isConnected()) {
      hlsConfig.loader = TunnelHlsLoader as unknown as typeof Hls.DefaultConfig.loader;
    }
    const hls = new Hls(hlsConfig);
    hlsRef.current = hls;
    hls.loadSource(hlsUrl);
    hls.attachMedia(videoEl);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      setLoading(false);
      videoEl.play().catch(() => {});
      onReady?.();
    });

    let mediaErrorRecoveries = 0;
    let networkRetries = 0;
    const MAX_NETWORK_RETRIES = 5;
    hls.on(Hls.Events.ERROR, async (_event, data) => {
      console.error("[HLS ERROR]", data.type, data.details, data.fatal, data.reason, data.response?.code);
      if (data.response?.code && [500, 410].includes(data.response.code)) {
        try {
          if (data.response.text) console.error("[HLS RESPONSE]", data.response.text);
        } catch {}
        try {
          const res = await apiFetch(`/api/hls/${streamId}/info`);
          const info = await res.json();
          if (info.error) console.error("[HLS SERVER ERROR]", info.error);
        } catch {}
      }
      if (!data.fatal) return;
      if (data.type === Hls.ErrorTypes.MEDIA_ERROR && mediaErrorRecoveries < 3) {
        mediaErrorRecoveries++;
        hls.recoverMediaError();
      } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.response?.code === 410) {
        hls.destroy();
        if (autoPlaySession) {
          tryNextAutoPlaySource();
        } else {
          setError("This source is not available. Please go back and try a different one.");
          setLoading(false);
        }
      } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.response?.code === 503 && networkRetries < MAX_NETWORK_RETRIES) {
        networkRetries++;
        setTimeout(() => hls.loadSource(hlsUrl), 2000);
      } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.response?.code === 500 && networkRetries < MAX_NETWORK_RETRIES) {
        networkRetries++;
        setTimeout(() => hls.loadSource(hlsUrl), 3000);
      } else {
        hls.destroy();
        if (autoPlaySession && data.type === Hls.ErrorTypes.NETWORK_ERROR) {
          tryNextAutoPlaySource();
        } else {
          const detail = data.reason || data.details || data.type;
          setError(
            data.type === Hls.ErrorTypes.NETWORK_ERROR
              ? `Stream failed: ${detail}`
              : `Playback failed: ${detail}`
          );
          setLoading(false);
        }
      }
    });

    return hls;
  }, [autoPlaySession, tryNextAutoPlaySource]);

  const serverSeek = useCallback(async (targetTime: number) => {
    if (!streamId) return;
    setIsSeeking(true);
    setLoadingMessage("Seeking...");
    setLoading(true);

    try {
      const resp = await apiFetch(`/api/hls/${streamId}/seek?t=${targetTime}&${codecParams}`);
      if (!resp.ok) throw new Error("Seek failed");

      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }

      const vid = videoRef.current;
      if (!vid) return;

      const hlsUrl = `/api/hls/${streamId}/master.m3u8?${codecParams}`;
      createHls(hlsUrl, vid, () => setIsSeeking(false));
    } catch {
      setIsSeeking(false);
      setLoading(false);
    }
  }, [streamId, codecParams, createHls]);

  const seekTo = useCallback((targetTime: number) => {
    const video = videoRef.current;
    if (!video || isSeeking) return;

    const bufferedEnd = video.buffered.length > 0
      ? video.buffered.end(video.buffered.length - 1)
      : video.duration;

    if (targetTime <= bufferedEnd + 5 && targetTime >= 0) {
      video.currentTime = Math.min(video.duration, Math.max(0, targetTime));
    } else if (realDuration > 0) {
      serverSeek(Math.max(0, Math.min(targetTime, realDuration)));
    }
  }, [isSeeking, realDuration, serverSeek]);

  // Init: fetch info then start HLS
  useEffect(() => {
    if (!streamId) {
      setError("No stream specified");
      setLoading(false);
      return;
    }
    setError("");

    let cancelled = false;

    async function init() {
      try {
        setLoadingMessage("Analyzing stream...");
        const infoResp = await apiFetch(`/api/hls/${streamId}/info`);
        if (infoResp.ok) {
          const info: StreamInfo = await infoResp.json();
          setStreamInfo(info);
          if (info.probe_failed || info.failed) {
            if (autoPlaySession) {
              tryNextAutoPlaySource();
              return;
            }
            setError(info.error || "Could not reach the source — the link may have expired. Please go back and try a different one.");
            setLoading(false);
            return;
          }
          if (info.decision) {
            const isRemux = info.decision.startsWith("remux");
            setLoadingMessage(isRemux ? "Starting stream..." : "Transcoding stream...");
          }
        }
      } catch { /* continue */ }

      if (cancelled) return;

      const video = videoRef.current;
      if (!video) return;

      setLoadingMessage("Buffering...");
      const hlsUrl = `/api/hls/${streamId}/master.m3u8?${codecParams}`;

      if (Hls.isSupported()) {
        createHls(hlsUrl, video);
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = hlsUrl;
        video.addEventListener("loadedmetadata", () => {
          setLoading(false);
          video.play().catch(() => {});
        });
      } else {
        setError("Your browser does not support HLS playback");
        setLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [streamId, codecParams, createHls]);

  // Periodically refresh stream info (to update transcoded_seconds)
  useEffect(() => {
    if (!streamId) return;
    const interval = setInterval(async () => {
      try {
        const resp = await apiFetch(`/api/hls/${streamId}/info`);
        if (resp.ok) {
          const info: StreamInfo = await resp.json();
          setStreamInfo(info);
        }
      } catch { /* ignore */ }
    }, 5000);
    return () => clearInterval(interval);
  }, [streamId]);

  // Time update listener
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onTime = () => setCurrentTime(video.currentTime);
    const onPlay = () => setIsPaused(false);
    const onPause = () => setIsPaused(true);
    const onVolume = () => {
      setIsMuted(video.muted);
      setVolume(video.volume);
    };
    video.addEventListener("timeupdate", onTime);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("volumechange", onVolume);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("volumechange", onVolume);
    };
  }, []);

  // Progress reporting
  useEffect(() => {
    progressInterval.current = setInterval(reportProgress, 10000);
    return () => {
      if (progressInterval.current) clearInterval(progressInterval.current);
      reportProgress();
    };
  }, [reportProgress]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const video = videoRef.current;
      if (!video || isSeeking) return;
      switch (e.key) {
        case " ":
        case "k":
          e.preventDefault();
          video.paused ? video.play() : video.pause();
          break;
        case "ArrowLeft":
          e.preventDefault();
          seekTo(video.currentTime - 10);
          break;
        case "ArrowRight":
          e.preventDefault();
          seekTo(video.currentTime + 10);
          break;
        case "f":
          e.preventDefault();
          document.fullscreenElement ? document.exitFullscreen() : video.requestFullscreen();
          break;
        case "Escape":
          if (showInfo) {
            setShowInfo(false);
          } else if (!document.fullscreenElement) {
            navigate(-1);
          }
          break;
        case "m":
          e.preventDefault();
          video.muted = !video.muted;
          break;
        case "i":
          e.preventDefault();
          setShowInfo(p => !p);
          break;
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [navigate, isSeeking, seekTo, showInfo]);

  const handleMouseMove = () => {
    setShowControls(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setShowControls(false), 3000);
  };

  const handleBack = () => {
    reportProgress();
    if (streamId) {
      apiFetch(`/api/hls/${streamId}/stop`).catch(() => {});
    }
    navigate(-1);
  };

  const handleSeekBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!seekBarRef.current || effectiveDuration <= 0) return;
    const rect = seekBarRef.current.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seekTo(pct * effectiveDuration);
  };

  const progressPct = effectiveDuration > 0 ? (currentTime / effectiveDuration) * 100 : 0;
  const transcodedPct = (streamInfo?.transcoded_seconds && effectiveDuration > 0)
    ? (streamInfo.transcoded_seconds / effectiveDuration) * 100
    : 100;

  if (error) {
    return (
      <div className="fixed inset-0 bg-black flex items-center justify-center z-50">
        <div className="text-center">
          <p className="text-red-400 text-lg mb-4">{error}</p>
          <button onClick={() => navigate(-1)} className="text-ink-300 hover:text-white transition-colors">
            Go back
          </button>
        </div>
      </div>
    );
  }

  const methodInfo = streamInfo?.decision ? describeMethod(streamInfo.decision) : null;

  return (
    <div
      className="fixed inset-0 bg-black z-50"
      onMouseMove={handleMouseMove}
      style={{ cursor: showControls ? "default" : "none" }}
    >
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
            <p className="text-ink-400 text-sm">{loadingMessage}</p>
          </div>
        </div>
      )}

      <video
        ref={videoRef}
        className="w-full h-full"
        playsInline
        onClick={() => {
          const v = videoRef.current;
          if (v) v.paused ? v.play() : v.pause();
        }}
        onDoubleClick={() => {
          const v = videoRef.current;
          if (v) document.fullscreenElement ? document.exitFullscreen() : v.requestFullscreen();
        }}
        onEnded={() => {
          reportProgress();
          if (externalId && providerKey) {
            api.markWatched({
              provider_key: providerKey,
              content_type: contentType,
              external_id: externalId,
              series_external_id: seriesExternalId,
              season_number: seasonNumber,
              episode_number: episodeNumber,
            }).catch(() => {});
          }
        }}
      />

      {/* Top bar: title + info button */}
      <div
        className={`absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 to-transparent transition-opacity duration-300 ${
          showControls ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      >
        <div className="flex items-center gap-3">
          <button onClick={handleBack} className="text-white/80 hover:text-white transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path fillRule="evenodd" d="M7.72 12.53a.75.75 0 010-1.06l7.5-7.5a.75.75 0 111.06 1.06L9.31 12l6.97 6.97a.75.75 0 11-1.06 1.06l-7.5-7.5z" clipRule="evenodd" />
            </svg>
          </button>
          <h2 className="text-white text-lg font-medium truncate flex-1">{title}</h2>
          <button
            onClick={() => setShowInfo(p => !p)}
            className={`text-sm px-3 py-1 rounded transition-colors ${
              showInfo ? "bg-white/20 text-white" : "text-white/60 hover:text-white hover:bg-white/10"
            }`}
            title="Playback info (I)"
          >
            Info
          </button>
        </div>
      </div>

      {/* Bottom controls: seek bar + play/pause + time + volume */}
      <div
        className={`absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent pt-16 pb-4 px-4 transition-opacity duration-300 ${
          showControls ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      >
        {/* Seek bar */}
        <div
          ref={seekBarRef}
          className="relative w-full h-6 flex items-center cursor-pointer group mb-2"
          onClick={handleSeekBarClick}
        >
          <div className="absolute inset-x-0 h-1 bg-white/20 rounded-full group-hover:h-1.5 transition-all">
            {/* Transcoded extent (lighter) */}
            <div
              className="absolute inset-y-0 left-0 bg-white/30 rounded-full"
              style={{ width: `${Math.min(100, transcodedPct)}%` }}
            />
            {/* Playback progress (bright) */}
            <div
              className="absolute inset-y-0 left-0 bg-brand-500 rounded-full"
              style={{ width: `${Math.min(100, progressPct)}%` }}
            />
          </div>
          {/* Scrubber thumb */}
          <div
            className="absolute w-3 h-3 bg-brand-500 rounded-full -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
            style={{ left: `${Math.min(100, progressPct)}%` }}
          />
        </div>

        <div className="flex items-center gap-4">
          {/* Play/Pause */}
          <button
            onClick={() => {
              const v = videoRef.current;
              if (v) v.paused ? v.play() : v.pause();
            }}
            className="text-white/90 hover:text-white transition-colors"
          >
            {isPaused ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
                <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
                <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
              </svg>
            )}
          </button>

          {/* Volume */}
          <button
            onClick={() => {
              const v = videoRef.current;
              if (v) v.muted = !v.muted;
            }}
            className="text-white/70 hover:text-white transition-colors"
          >
            {isMuted || volume === 0 ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.348 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM17.78 9.22a.75.75 0 10-1.06 1.06L18.44 12l-1.72 1.72a.75.75 0 001.06 1.06l1.72-1.72 1.72 1.72a.75.75 0 101.06-1.06L20.56 12l1.72-1.72a.75.75 0 00-1.06-1.06l-1.72 1.72-1.72-1.72z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.348 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0c3.808 3.807 3.808 9.98 0 13.788a.75.75 0 01-1.06-1.06 8.25 8.25 0 000-11.668.75.75 0 010-1.06z" />
                <path d="M15.932 7.757a.75.75 0 011.061 0 6 6 0 010 8.486.75.75 0 01-1.06-1.061 4.5 4.5 0 000-6.364.75.75 0 010-1.06z" />
              </svg>
            )}
          </button>

          {/* Time */}
          <span className="text-white/80 text-sm font-mono tabular-nums select-none">
            {formatTime(currentTime)} / {formatTime(effectiveDuration)}
          </span>

          <div className="flex-1" />

          {/* Method badge */}
          {methodInfo && (
            <span className={`text-xs px-2 py-0.5 rounded select-none ${
              methodInfo.method === "Remux"
                ? "bg-emerald-500/20 text-emerald-400"
                : methodInfo.method === "Partial Transcode"
                  ? "bg-amber-500/20 text-amber-400"
                  : "bg-red-500/20 text-red-400"
            }`}>
              {methodInfo.method}
            </span>
          )}

          {/* Fullscreen */}
          <button
            onClick={() => {
              const v = videoRef.current;
              if (v) document.fullscreenElement ? document.exitFullscreen() : v.requestFullscreen();
            }}
            className="text-white/70 hover:text-white transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path fillRule="evenodd" d="M4.5 5.653c0-.526.214-1.003.56-1.348A1.903 1.903 0 016.406 3.75H9a.75.75 0 010 1.5H6.406a.403.403 0 00-.406.403V9a.75.75 0 01-1.5 0V5.653zM15 4.5a.75.75 0 01.75-.75h2.594c.528 0 1.006.214 1.35.56.346.345.556.82.556 1.343V9a.75.75 0 01-1.5 0V5.653a.403.403 0 00-.406-.403H15.75A.75.75 0 0115 4.5zM4.5 15a.75.75 0 01.75.75V18.347c0 .223.182.403.406.403H9a.75.75 0 010 1.5H6.406A1.906 1.906 0 014.5 18.347V15.75A.75.75 0 014.5 15zm15 0a.75.75 0 01.75.75v2.597a1.906 1.906 0 01-1.906 1.903H15.75a.75.75 0 010-1.5h2.594a.403.403 0 00.406-.403V15.75a.75.75 0 01.75-.75z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      {/* Playback Info Panel */}
      {showInfo && streamInfo && (
        <div className="absolute top-16 right-4 w-80 bg-black/90 border border-white/10 rounded-lg p-4 z-30 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-white text-sm font-semibold">Playback Info</h3>
            <button
              onClick={() => setShowInfo(false)}
              className="text-white/40 hover:text-white/80 transition-colors text-xs"
            >
              Close
            </button>
          </div>

          <div className="space-y-2.5 text-xs">
            {/* Method */}
            {methodInfo && (
              <div>
                <div className="text-white/40 mb-0.5">Playback Method</div>
                <div className={`font-medium ${
                  methodInfo.method === "Remux"
                    ? "text-emerald-400"
                    : methodInfo.method === "Partial Transcode"
                      ? "text-amber-400"
                      : methodInfo.method.includes("Transcode")
                        ? "text-red-400"
                        : "text-white/80"
                }`}>
                  {methodInfo.method}
                </div>
                {methodInfo.reason && (
                  <div className="text-white/50 mt-0.5 leading-relaxed">{methodInfo.reason}</div>
                )}
              </div>
            )}

            {/* Source codecs */}
            <div className="flex gap-4">
              <div>
                <div className="text-white/40 mb-0.5">Video</div>
                <div className="text-white/80">{streamInfo.video_codec.toUpperCase() || "Unknown"}</div>
              </div>
              <div>
                <div className="text-white/40 mb-0.5">Audio</div>
                <div className="text-white/80">{streamInfo.audio_codec.toUpperCase() || "Unknown"}</div>
              </div>
              {streamInfo.width > 0 && (
                <div>
                  <div className="text-white/40 mb-0.5">Resolution</div>
                  <div className="text-white/80">{streamInfo.width}x{streamInfo.height}</div>
                </div>
              )}
            </div>

            {/* Duration */}
            {streamInfo.duration_seconds > 0 && (
              <div>
                <div className="text-white/40 mb-0.5">Duration</div>
                <div className="text-white/80">{formatTime(streamInfo.duration_seconds)}</div>
              </div>
            )}

            {/* Transcode progress */}
            {streamInfo.is_running && streamInfo.transcoded_seconds != null && streamInfo.duration_seconds > 0 && (
              <div>
                <div className="text-white/40 mb-0.5">Transcoded</div>
                <div className="text-white/80">
                  {formatTime(streamInfo.transcoded_seconds)} / {formatTime(streamInfo.duration_seconds)}
                  {" "}({Math.round((streamInfo.transcoded_seconds / streamInfo.duration_seconds) * 100)}%)
                </div>
              </div>
            )}

            {/* Client codecs */}
            <div>
              <div className="text-white/40 mb-0.5">Browser Codecs</div>
              <div className="text-white/60">
                V: {clientCodecs.vc} | A: {clientCodecs.ac}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
