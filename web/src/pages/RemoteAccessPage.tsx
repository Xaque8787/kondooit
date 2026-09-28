import { useEffect, useState, useCallback } from "react";
import { api } from "../api";
import { LoadingSpinner } from "../components/ui";

interface RemoteStatus {
  enabled: boolean;
  online: boolean;
  endpoint_id: string | null;
  relay_connected: boolean;
}

export function RemoteAccessPage() {
  const [status, setStatus] = useState<RemoteStatus | null>(null);
  const [connectionUrl, setConnectionUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.remoteAccessStatus();
      setStatus(s);
      if (s.enabled && s.online) {
        const urlRes = await api.remoteAccessConnectionUrl();
        setConnectionUrl(urlRes.url);
      } else {
        setConnectionUrl("");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch status");
    }
  }, []);

  useEffect(() => {
    fetchStatus().finally(() => setLoading(false));
  }, [fetchStatus]);

  useEffect(() => {
    if (!status?.enabled || !status?.online) return;
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, [status?.enabled, status?.online, fetchStatus]);

  const handleToggle = async () => {
    if (!status) return;
    setToggling(true);
    setError("");
    try {
      if (status.enabled) {
        await api.remoteAccessDisable();
      } else {
        await api.remoteAccessEnable();
      }
      await new Promise((r) => setTimeout(r, 1500));
      await fetchStatus();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to toggle remote access");
    } finally {
      setToggling(false);
    }
  };

  const handleCopy = async () => {
    if (!connectionUrl) return;
    try {
      await navigator.clipboard.writeText(connectionUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const el = document.createElement("textarea");
      el.value = connectionUrl;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink-100">Remote Access</h1>
        <p className="text-ink-400 mt-1">
          Connect to your Kondooit server from anywhere using an encrypted
          peer-to-peer connection. No port forwarding or VPN required.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Enable/Disable Toggle */}
      <div className="bg-ink-900 border border-ink-800 rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink-100">
              Remote Access
            </h2>
            <p className="text-sm text-ink-400 mt-0.5">
              Allow connections from outside your local network
            </p>
          </div>
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              status?.enabled ? "bg-brand-600" : "bg-ink-700"
            } ${toggling ? "opacity-50 cursor-wait" : ""}`}
          >
            <span
              className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                status?.enabled ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Status Section */}
      {status?.enabled && (
        <div className="bg-ink-900 border border-ink-800 rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-ink-100">Status</h2>
          <div className="grid grid-cols-2 gap-4">
            <StatusItem
              label="Connection"
              value={status.online ? "Online" : "Connecting..."}
              ok={status.online}
            />
            <StatusItem
              label="Relay"
              value={status.relay_connected ? "Connected" : "Waiting..."}
              ok={status.relay_connected}
            />
          </div>
          {status.endpoint_id && (
            <div className="pt-2 border-t border-ink-800">
              <span className="text-xs text-ink-500 font-mono break-all">
                Endpoint: {status.endpoint_id.slice(0, 16)}...
              </span>
            </div>
          )}
        </div>
      )}

      {/* Connection Link */}
      {status?.enabled && status.online && connectionUrl && (
        <div className="bg-ink-900 border border-ink-800 rounded-xl p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-ink-100">
              Browser Connection
            </h2>
            <p className="text-sm text-ink-400 mt-0.5">
              Share this link to connect from another device. Anyone with the
              link can reach this server, but they still need to sign in.
            </p>
          </div>
          <div className="bg-ink-950 rounded-lg p-3 border border-ink-700">
            <code className="text-xs text-ink-300 break-all leading-relaxed block">
              {connectionUrl}
            </code>
          </div>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {copied ? (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Copied
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Copy Connection Link
              </>
            )}
          </button>
        </div>
      )}

      {/* How It Works */}
      <div className="bg-ink-900/50 border border-ink-800/50 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-ink-300 uppercase tracking-wider mb-3">
          How it works
        </h3>
        <ol className="space-y-2 text-sm text-ink-400">
          <li className="flex gap-3">
            <span className="text-brand-400 font-semibold shrink-0">1.</span>
            Enable remote access above. Your server connects to a relay.
          </li>
          <li className="flex gap-3">
            <span className="text-brand-400 font-semibold shrink-0">2.</span>
            Copy the connection link and send it to whoever needs access.
          </li>
          <li className="flex gap-3">
            <span className="text-brand-400 font-semibold shrink-0">3.</span>
            They open the link in their browser and sign in with their Kondooit account.
          </li>
          <li className="flex gap-3">
            <span className="text-brand-400 font-semibold shrink-0">4.</span>
            All traffic is end-to-end encrypted. The relay cannot see your data.
          </li>
        </ol>
      </div>
    </div>
  );
}

function StatusItem({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={`w-2 h-2 rounded-full shrink-0 ${
          ok ? "bg-green-400" : "bg-amber-400 animate-pulse"
        }`}
      />
      <div>
        <p className="text-xs text-ink-500">{label}</p>
        <p className="text-sm text-ink-200 font-medium">{value}</p>
      </div>
    </div>
  );
}
