import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Hls from "hls.js";
import { api } from "../api";

export function PlayerPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const progressInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const streamId = params.get("stream");
  const title = params.get("title") || "Untitled";
  const providerKey = params.get("provider") || "";
  const contentType = params.get("type") || "movie";
  const externalId = parseInt(params.get("eid") || "0", 10);
  const seriesExternalId = params.get("series_eid") ? parseInt(params.get("series_eid")!, 10) : undefined;
  const seasonNumber = params.get("season") ? parseInt(params.get("season")!, 10) : undefined;
  const episodeNumber = params.get("episode") ? parseInt(params.get("episode")!, 10) : undefined;

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reportProgress = useCallback(() => {
    const video = videoRef.current;
    if (!video || !providerKey || !externalId) return;
    const pos = Math.floor(video.currentTime);
    const dur = Math.floor(video.duration) || 0;
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
  }, [providerKey, contentType, externalId, seriesExternalId, seasonNumber, episodeNumber]);

  useEffect(() => {
    if (!streamId) {
      setError("No stream specified");
      setLoading(false);
      return;
    }

    const video = videoRef.current;
    if (!video) return;

    const hlsUrl = `/api/hls/${streamId}/master.m3u8`;

    if (Hls.isSupported()) {
      const hls = new Hls({
        maxBufferLength: 30,
        maxMaxBufferLength: 120,
        startLevel: -1,
        startPosition: 0,
        liveSyncDuration: 0,
        liveMaxLatencyDuration: Infinity,
        manifestLoadingRetryDelay: 2000,
        manifestLoadingMaxRetry: 30,
        debug: false,
      });
      hlsRef.current = hls;

      hls.loadSource(hlsUrl);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false);
        video.play().catch(() => {});
      });

      let mediaErrorRecoveries = 0;
      hls.on(Hls.Events.ERROR, (_event, data) => {
        console.error("[HLS ERROR]", data.type, data.details, data.fatal, data.reason, data.response?.code, data);
        if (data.fatal) {
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR && mediaErrorRecoveries < 3) {
            mediaErrorRecoveries++;
            console.warn(`[HLS] Recovering from media error (attempt ${mediaErrorRecoveries})`);
            hls.recoverMediaError();
          } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.response?.code === 503) {
            setTimeout(() => hls.loadSource(hlsUrl), 2000);
          } else {
            const detail = data.reason || data.details || data.type;
            setError(
              data.type === Hls.ErrorTypes.NETWORK_ERROR
                ? `Network error: ${detail}`
                : `Playback failed: ${detail}`
            );
            setLoading(false);
          }
        }
      });

      return () => {
        hls.destroy();
        hlsRef.current = null;
      };
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
  }, [streamId]);

  useEffect(() => {
    progressInterval.current = setInterval(reportProgress, 10000);
    return () => {
      if (progressInterval.current) clearInterval(progressInterval.current);
      reportProgress();
    };
  }, [reportProgress]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const video = videoRef.current;
      if (!video) return;
      switch (e.key) {
        case " ":
        case "k":
          e.preventDefault();
          video.paused ? video.play() : video.pause();
          break;
        case "ArrowLeft":
          e.preventDefault();
          video.currentTime = Math.max(0, video.currentTime - 10);
          break;
        case "ArrowRight":
          e.preventDefault();
          video.currentTime = Math.min(video.duration, video.currentTime + 10);
          break;
        case "f":
          e.preventDefault();
          document.fullscreenElement ? document.exitFullscreen() : video.requestFullscreen();
          break;
        case "Escape":
          if (!document.fullscreenElement) navigate(-1);
          break;
        case "m":
          e.preventDefault();
          video.muted = !video.muted;
          break;
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [navigate]);

  const handleMouseMove = () => {
    setShowControls(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setShowControls(false), 3000);
  };

  const handleBack = () => {
    reportProgress();
    if (streamId) {
      fetch(`/api/hls/${streamId}/stop`).catch(() => {});
    }
    navigate(-1);
  };

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

  return (
    <div
      className="fixed inset-0 bg-black z-50 cursor-none"
      onMouseMove={handleMouseMove}
      style={{ cursor: showControls ? "default" : "none" }}
    >
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
            <p className="text-ink-400 text-sm">Preparing stream...</p>
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

      <div
        className={`absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 to-transparent transition-opacity duration-300 ${
          showControls ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="text-white/80 hover:text-white transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path fillRule="evenodd" d="M7.72 12.53a.75.75 0 010-1.06l7.5-7.5a.75.75 0 111.06 1.06L9.31 12l6.97 6.97a.75.75 0 11-1.06 1.06l-7.5-7.5z" clipRule="evenodd" />
            </svg>
          </button>
          <h2 className="text-white text-lg font-medium truncate">{title}</h2>
        </div>
      </div>
    </div>
  );
}
