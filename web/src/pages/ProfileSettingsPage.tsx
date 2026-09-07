import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";
import type { Profile } from "../types";

const AVATAR_COLORS = [
  "#3B82F6", "#EF4444", "#10B981", "#F59E0B",
  "#8B5CF6", "#EC4899", "#06B6D4", "#F97316",
];

const RESOLUTION_OPTIONS = [
  { value: 2160, label: "4K (2160p)" },
  { value: 1080, label: "1080p" },
  { value: 720, label: "720p" },
  { value: 480, label: "480p" },
];

export function ProfileSettingsPage() {
  const { activeProfile, selectProfile } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const [displayName, setDisplayName] = useState("");
  const [avatarColor, setAvatarColor] = useState("#3B82F6");
  const [maxResolution, setMaxResolution] = useState(2160);
  const [allowDirectPlay, setAllowDirectPlay] = useState(true);
  const [allowRemux, setAllowRemux] = useState(true);
  const [allowTranscode, setAllowTranscode] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);

  useEffect(() => {
    if (!activeProfile) return;
    setLoading(true);
    api.getProfile(activeProfile.id)
      .then((p) => {
        setProfile(p);
        setDisplayName(p.display_name);
        setAvatarColor(p.avatar_color);
        setMaxResolution(p.max_resolution);
        setAllowDirectPlay(p.allow_direct_play);
        setAllowRemux(p.allow_remux);
        setAllowTranscode(p.allow_transcode);
        setAutoPlay(p.auto_play);
      })
      .catch(() => setError("Failed to load profile"))
      .finally(() => setLoading(false));
  }, [activeProfile]);

  const handleSave = async () => {
    if (!activeProfile || !profile) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateProfile(activeProfile.id, {
        display_name: displayName.trim(),
        avatar_color: avatarColor,
        max_resolution: maxResolution,
        allow_direct_play: allowDirectPlay,
        allow_remux: allowRemux,
        allow_transcode: allowTranscode,
        auto_play: autoPlay,
      });
      setProfile(updated);
      selectProfile({
        id: updated.id,
        display_name: updated.display_name,
        avatar_color: updated.avatar_color,
        is_admin: updated.is_admin,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-ink-700 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!profile || !activeProfile) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <p className="text-ink-400">No profile selected.</p>
      </div>
    );
  }

  const videoCodecs = profile.client_video_codecs ? profile.client_video_codecs.split(",") : [];
  const audioCodecs = profile.client_audio_codecs ? profile.client_audio_codecs.split(",") : [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => navigate(-1)}
          className="text-ink-400 hover:text-ink-200 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M7.72 12.53a.75.75 0 010-1.06l7.5-7.5a.75.75 0 111.06 1.06L9.31 12l6.97 6.97a.75.75 0 11-1.06 1.06l-7.5-7.5z" clipRule="evenodd" />
          </svg>
        </button>
        <h1 className="text-2xl font-bold text-ink-100">Profile Settings</h1>
      </div>

      <div className="space-y-8">
        {/* Identity */}
        <section className="bg-ink-900 rounded-xl border border-ink-700 p-6">
          <h2 className="text-lg font-semibold text-ink-100 mb-4">Identity</h2>

          <div className="flex items-start gap-6">
            <div
              className="w-20 h-20 rounded-2xl flex items-center justify-center text-2xl font-bold text-white shrink-0"
              style={{ backgroundColor: avatarColor }}
            >
              {displayName.charAt(0).toUpperCase() || "?"}
            </div>

            <div className="flex-1 space-y-4">
              <div>
                <label className="block text-sm text-ink-400 mb-1">Display name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  maxLength={100}
                  className="w-full px-3 py-2 bg-ink-800 border border-ink-600 rounded-lg text-ink-100 placeholder-ink-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div>
                <label className="block text-sm text-ink-400 mb-2">Avatar color</label>
                <div className="flex gap-2 flex-wrap">
                  {AVATAR_COLORS.map((color) => (
                    <button
                      key={color}
                      onClick={() => setAvatarColor(color)}
                      className={`w-8 h-8 rounded-full transition-all ${
                        avatarColor === color
                          ? "ring-2 ring-white ring-offset-2 ring-offset-ink-900 scale-110"
                          : "hover:scale-110"
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Playback Preferences */}
        <section className="bg-ink-900 rounded-xl border border-ink-700 p-6">
          <h2 className="text-lg font-semibold text-ink-100 mb-1">Playback Preferences</h2>
          <p className="text-sm text-ink-500 mb-5">
            Control how media is processed before it reaches your screen.
          </p>

          <div className="space-y-5">
            {/* Max Resolution */}
            <div>
              <label className="block text-sm text-ink-300 mb-2">Maximum resolution</label>
              <div className="flex gap-2 flex-wrap">
                {RESOLUTION_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setMaxResolution(opt.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      maxResolution === opt.value
                        ? "bg-brand-500 text-white"
                        : "bg-ink-800 text-ink-300 hover:bg-ink-700 hover:text-ink-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Playback method toggles */}
            <div className="space-y-3">
              <Toggle
                label="Direct Play"
                description="Play media files without any server processing. Best quality, zero CPU usage."
                checked={allowDirectPlay}
                onChange={setAllowDirectPlay}
              />
              <Toggle
                label="Remux"
                description="Repackage the media into a different container without re-encoding. Near-zero CPU, no quality loss."
                checked={allowRemux}
                onChange={setAllowRemux}
              />
              <Toggle
                label="Transcode"
                description="Re-encode video or audio when your device cannot play the original format. Uses significant server CPU."
                checked={allowTranscode}
                onChange={setAllowTranscode}
              />
            </div>

            {!allowDirectPlay && !allowRemux && !allowTranscode && (
              <p className="text-sm text-amber-400 bg-amber-500/10 rounded-lg px-3 py-2">
                All playback methods are disabled. You will not be able to play any media.
              </p>
            )}
          </div>
        </section>

        {/* Auto Play */}
        <section className="bg-ink-900 rounded-xl border border-ink-700 p-6">
          <h2 className="text-lg font-semibold text-ink-100 mb-1">Auto Play</h2>
          <p className="text-sm text-ink-500 mb-5">
            When enabled, the system will automatically pick the best source and start playing.
            Sources are selected based on your playback preferences above.
          </p>

          <Toggle
            label="Enable Auto Play"
            description="Automatically select and play the best matching source when you choose to watch something."
            checked={autoPlay}
            onChange={setAutoPlay}
          />
        </section>

        {/* Client Capabilities (read-only) */}
        {(videoCodecs.length > 0 || audioCodecs.length > 0) && (
          <section className="bg-ink-900 rounded-xl border border-ink-700 p-6">
            <h2 className="text-lg font-semibold text-ink-100 mb-1">Browser Capabilities</h2>
            <p className="text-sm text-ink-500 mb-4">
              Detected automatically from your browser. These determine which formats
              can be played directly without server processing.
            </p>

            <div className="flex gap-8">
              {videoCodecs.length > 0 && (
                <div>
                  <span className="text-xs text-ink-500 uppercase tracking-wider">Video</span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {videoCodecs.map((c) => (
                      <span key={c} className="px-2 py-0.5 bg-ink-800 text-ink-300 text-xs rounded">
                        {c.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {audioCodecs.length > 0 && (
                <div>
                  <span className="text-xs text-ink-500 uppercase tracking-wider">Audio</span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {audioCodecs.map((c) => (
                      <span key={c} className="px-2 py-0.5 bg-ink-800 text-ink-300 text-xs rounded">
                        {c.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Save */}
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !displayName.trim()}
            className="btn-primary px-6"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
          {saved && (
            <span className="text-sm text-emerald-400 animate-pulse">Saved</span>
          )}
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div className="pt-0.5">
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            checked ? "bg-brand-500" : "bg-ink-700"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
              checked ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>
      <div className="flex-1 select-none" onClick={() => onChange(!checked)}>
        <div className="text-sm font-medium text-ink-200 group-hover:text-ink-100 transition-colors">
          {label}
        </div>
        <div className="text-xs text-ink-500 mt-0.5 leading-relaxed">{description}</div>
      </div>
    </label>
  );
}
