import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getTunnelServerIdFromUrl,
  initTunnel,
  type TunnelStatus,
  onTunnelStatus,
} from "../tunnel";

const PHASE_LABELS: Record<string, string> = {
  idle: "Preparing...",
  "loading-wasm": "Loading runtime...",
  "creating-endpoint": "Creating secure endpoint...",
  connecting: "Connecting to your server...",
  connected: "Connected!",
  error: "Connection failed",
};

export function TunnelConnectPage() {
  const [status, setStatus] = useState<TunnelStatus>({ phase: "idle" });
  const navigate = useNavigate();

  useEffect(() => {
    const serverId = getTunnelServerIdFromUrl();
    if (!serverId) {
      setStatus({ phase: "error", message: "No server ID provided in URL." });
      return;
    }

    onTunnelStatus(setStatus);

    initTunnel(serverId)
      .then(() => {
        setTimeout(() => navigate("/login", { replace: true }), 600);
      })
      .catch(() => {
        // error status already set by initTunnel
      });
  }, [navigate]);

  const phaseIndex = ["idle", "loading-wasm", "creating-endpoint", "connecting", "connected"].indexOf(status.phase);
  const steps = [
    { key: "loading-wasm", label: "Loading runtime" },
    { key: "creating-endpoint", label: "Creating endpoint" },
    { key: "connecting", label: "Connecting to server" },
    { key: "connected", label: "Connected" },
  ];

  return (
    <div className="min-h-screen bg-ink-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-ink-50 tracking-tight">
            Kondooit
          </h1>
          <p className="text-ink-400 mt-1 text-sm">Remote Access</p>
        </div>

        <div className="bg-ink-900/60 border border-ink-800 rounded-xl p-8">
          <div className="space-y-4">
            {steps.map((step, i) => {
              const stepIndex = i + 1;
              const isActive = status.phase === step.key;
              const isDone = phaseIndex > stepIndex;
              const isPending = phaseIndex < stepIndex;

              return (
                <div key={step.key} className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors duration-300 ${
                      isDone
                        ? "bg-emerald-500/20 text-emerald-400"
                        : isActive
                          ? "bg-brand-500/20 text-brand-400"
                          : "bg-ink-800 text-ink-600"
                    }`}
                  >
                    {isDone ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : isActive ? (
                      <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-current opacity-40" />
                    )}
                  </div>
                  <span
                    className={`text-sm transition-colors duration-300 ${
                      isDone
                        ? "text-ink-300"
                        : isActive
                          ? "text-ink-100 font-medium"
                          : isPending
                            ? "text-ink-600"
                            : "text-ink-400"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>

          {status.phase === "error" && (
            <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-red-400 text-sm font-medium">
                {PHASE_LABELS.error}
              </p>
              <p className="text-red-400/70 text-xs mt-1">
                {"message" in status ? status.message : "Unknown error"}
              </p>
              <button
                onClick={() => window.location.reload()}
                className="mt-3 px-4 py-1.5 bg-ink-800 text-ink-200 text-sm rounded-lg hover:bg-ink-700 transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {"serverId" in status && status.phase === "connected" && (
            <div className="mt-6 text-center">
              <p className="text-emerald-400 text-sm font-medium">
                Redirecting to login...
              </p>
            </div>
          )}
        </div>

        <p className="text-center text-ink-600 text-xs mt-6">
          Secure peer-to-peer connection via iroh
        </p>
      </div>
    </div>
  );
}
