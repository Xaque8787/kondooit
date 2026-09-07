import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";

const AVATAR_COLORS = [
  "#3B82F6", "#EF4444", "#10B981", "#F59E0B",
  "#8B5CF6", "#EC4899", "#06B6D4", "#F97316",
];

export function ProfileSelectPage() {
  const { user, selectProfile, logout, clearProfile } = useAuth();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(AVATAR_COLORS[0]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  if (!user) return null;

  const handleSelect = (profile: (typeof user.profiles)[0]) => {
    selectProfile(profile);
    navigate("/");
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      const created = await api.createProfile({
        display_name: newName.trim(),
        avatar_color: newColor,
      });
      selectProfile({
        id: created.id,
        display_name: created.display_name,
        avatar_color: created.avatar_color,
        is_admin: created.is_admin,
      });
      navigate("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create profile");
    } finally {
      setCreating(false);
    }
  };

  const handleLogout = () => {
    clearProfile();
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl">
        <h1 className="text-3xl font-bold text-ink-100 text-center mb-2">
          Who's watching?
        </h1>
        <p className="text-ink-400 text-center mb-10">
          Select a profile to continue
        </p>

        <div className="flex flex-wrap justify-center gap-6 mb-10">
          {user.profiles.map((profile) => (
            <button
              key={profile.id}
              onClick={() => handleSelect(profile)}
              className="group flex flex-col items-center gap-3 focus:outline-none"
            >
              <div
                className="w-24 h-24 rounded-2xl flex items-center justify-center text-3xl font-bold text-white transition-all group-hover:ring-4 group-hover:ring-white/30 group-hover:scale-105"
                style={{ backgroundColor: profile.avatar_color }}
              >
                {profile.display_name.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm text-ink-300 group-hover:text-ink-100 transition-colors">
                {profile.display_name}
              </span>
            </button>
          ))}

          {user.profiles.length < 8 && !showCreate && (
            <button
              onClick={() => setShowCreate(true)}
              className="group flex flex-col items-center gap-3 focus:outline-none"
            >
              <div className="w-24 h-24 rounded-2xl flex items-center justify-center text-3xl border-2 border-dashed border-ink-600 text-ink-500 transition-all group-hover:border-ink-400 group-hover:text-ink-300 group-hover:scale-105">
                +
              </div>
              <span className="text-sm text-ink-500 group-hover:text-ink-300 transition-colors">
                Add Profile
              </span>
            </button>
          )}
        </div>

        {showCreate && (
          <div className="mx-auto max-w-sm bg-ink-900 rounded-xl p-6 border border-ink-700">
            <h2 className="text-lg font-semibold text-ink-100 mb-4">
              New Profile
            </h2>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Profile name"
              maxLength={100}
              className="w-full px-3 py-2 bg-ink-800 border border-ink-600 rounded-lg text-ink-100 placeholder-ink-500 focus:outline-none focus:ring-2 focus:ring-brand-500 mb-4"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
            />

            <div className="mb-4">
              <p className="text-xs text-ink-400 mb-2">Avatar color</p>
              <div className="flex gap-2 flex-wrap">
                {AVATAR_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNewColor(color)}
                    className={`w-8 h-8 rounded-full transition-all ${
                      newColor === color
                        ? "ring-2 ring-white ring-offset-2 ring-offset-ink-900 scale-110"
                        : "hover:scale-110"
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-400 mb-3">{error}</p>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="btn-primary flex-1 text-sm"
              >
                {creating ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => { setShowCreate(false); setNewName(""); setError(""); }}
                className="btn-ghost text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="text-center mt-10">
          <button
            onClick={handleLogout}
            className="text-sm text-ink-500 hover:text-ink-300 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
