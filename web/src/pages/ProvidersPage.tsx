import { useEffect, useState } from "react";
import { api } from "../api";
import type {
  ProviderConfig,
  ProviderInfo,
  ScraperModule,
  SourceProviderConfig,
  SourceProviderInfo,
} from "../types";
import { LoadingSpinner, ErrorState } from "../components/ui";

function MetadataProviderSection() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [configs, setConfigs] = useState<Record<string, ProviderConfig>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState("disabled");
  const [priority, setPriority] = useState(100);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    api
      .listProviders()
      .then(async (ps) => {
        setProviders(ps);
        const configMap: Record<string, ProviderConfig> = {};
        for (const p of ps) {
          configMap[p.key] = await api.getProviderConfig(p.key);
        }
        setConfigs(configMap);
        if (ps.length > 0) {
          setActiveProvider(ps[0].key);
          setApiKey(configMap[ps[0].key]?.api_key || "");
          setStatus(configMap[ps[0].key]?.status || "disabled");
          setPriority(configMap[ps[0].key]?.priority ?? 100);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const selectProvider = (key: string) => {
    setActiveProvider(key);
    setApiKey(configs[key]?.api_key || "");
    setStatus(configs[key]?.status || "disabled");
    setPriority(configs[key]?.priority ?? 100);
    setTestResult(null);
    setSaveMsg("");
  };

  const handleSave = async () => {
    if (!activeProvider) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const cfg = await api.saveProviderConfig(activeProvider, apiKey, status, priority);
      setConfigs((prev) => ({ ...prev, [activeProvider]: cfg }));
      setSaveMsg("Saved successfully");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!activeProvider) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testProvider(activeProvider);
      setTestResult(res.connected);
    } catch {
      setTestResult(false);
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading metadata providers" />;
  if (error) return <ErrorState message={error} />;
  if (providers.length === 0) return null;

  const active = providers.find((p) => p.key === activeProvider);

  return (
    <div>
      <h2 className="text-lg font-bold text-ink-100 mb-1">Metadata Providers</h2>
      <p className="text-sm text-ink-400 mb-5">
        Content discovery sources. Lower priority numbers are queried first.
      </p>
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="lg:w-56 shrink-0 space-y-2">
          {providers.map((p) => {
            const cfg = configs[p.key];
            const enabled = cfg?.status === "enabled";
            return (
              <button
                key={p.key}
                onClick={() => selectProvider(p.key)}
                className={`w-full text-left card p-4 transition-colors ${
                  activeProvider === p.key ? "border-brand-600" : "hover:border-ink-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink-100">{p.name}</span>
                  <span className={`badge ${enabled ? "bg-success-500/20 text-success-500" : "bg-ink-800 text-ink-500"}`}>
                    {enabled ? "On" : "Off"}
                  </span>
                </div>
                {cfg?.priority !== undefined && enabled && (
                  <span className="text-xs text-ink-500 mt-1 block">Priority: {cfg.priority}</span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex-1 min-w-0">
          {active && (
            <>
              <div className="mb-4">
                <h3 className="text-base font-bold text-ink-100">{active.name}</h3>
                <p className="text-sm text-ink-400 mt-1">{active.description}</p>
              </div>
              <div className="card p-6 space-y-5">
                <div>
                  <label className="block text-sm font-medium text-ink-300 mb-1.5">API Key</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter API key..."
                    className="input"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-300 mb-1.5">Status</label>
                    <select value={status} onChange={(e) => setStatus(e.target.value)} className="input">
                      <option value="disabled">Disabled</option>
                      <option value="enabled">Enabled</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-300 mb-1.5">Priority</label>
                    <input
                      type="number"
                      min={1}
                      max={999}
                      value={priority}
                      onChange={(e) => setPriority(parseInt(e.target.value, 10) || 100)}
                      className="input"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={handleSave} disabled={saving} className="btn-primary">
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button onClick={handleTest} disabled={testing || !apiKey} className="btn-secondary">
                    {testing ? "Testing..." : "Test connection"}
                  </button>
                </div>
                {saveMsg && <p className="text-sm text-success-500">{saveMsg}</p>}
                {testResult === true && <p className="text-sm text-success-500">Connection successful</p>}
                {testResult === false && (
                  <p className="text-sm text-error-400">Connection failed — check your API key</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceProviderSection() {
  const [providers, setProviders] = useState<SourceProviderInfo[]>([]);
  const [configs, setConfigs] = useState<Record<string, SourceProviderConfig>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("disabled");
  const [priority, setPriority] = useState(100);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    api
      .listSourceProviders()
      .then(async (ps) => {
        setProviders(ps);
        const configMap: Record<string, SourceProviderConfig> = {};
        for (const p of ps) {
          try {
            configMap[p.key] = await api.getSourceProviderConfig(p.key);
          } catch {
            configMap[p.key] = { key: p.key, credentials: {}, status: "disabled", priority: 100 };
          }
        }
        setConfigs(configMap);
        if (ps.length > 0) {
          setActiveProvider(ps[0].key);
          setCredentials(configMap[ps[0].key]?.credentials || {});
          setStatus(configMap[ps[0].key]?.status || "disabled");
          setPriority(configMap[ps[0].key]?.priority ?? 100);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const selectProvider = (key: string) => {
    setActiveProvider(key);
    setCredentials(configs[key]?.credentials || {});
    setStatus(configs[key]?.status || "disabled");
    setPriority(configs[key]?.priority ?? 100);
    setTestResult(null);
    setSaveMsg("");
  };

  const updateCredential = (field: string, value: string) => {
    setCredentials((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!activeProvider) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const cfg = await api.saveSourceProviderConfig(activeProvider, credentials, status, priority);
      setConfigs((prev) => ({ ...prev, [activeProvider]: cfg }));
      setSaveMsg("Saved successfully");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!activeProvider) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testSourceProvider(activeProvider);
      setTestResult(res.connected);
    } catch {
      setTestResult(false);
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading source providers" />;
  if (error) return <ErrorState message={error} />;
  if (providers.length === 0) return null;

  const active = providers.find((p) => p.key === activeProvider);
  const hasCredentials = active?.credential_fields.some(
    (f) => f.required && credentials[f.name]
  );

  return (
    <div>
      <h2 className="text-lg font-bold text-ink-100 mb-1">Source Providers</h2>
      <p className="text-sm text-ink-400 mb-5">
        Services that provide playable media sources. Configure credentials to enable.
      </p>
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="lg:w-56 shrink-0 space-y-2">
          {providers.map((p) => {
            const cfg = configs[p.key];
            const enabled = cfg?.status === "enabled";
            return (
              <button
                key={p.key}
                onClick={() => selectProvider(p.key)}
                className={`w-full text-left card p-4 transition-colors ${
                  activeProvider === p.key ? "border-brand-600" : "hover:border-ink-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink-100">{p.name}</span>
                  <span className={`badge ${enabled ? "bg-success-500/20 text-success-500" : "bg-ink-800 text-ink-500"}`}>
                    {enabled ? "On" : "Off"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {p.capabilities.map((c) => (
                    <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-ink-800/60 text-ink-500">
                      {c.replace("_", " ")}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>

        <div className="flex-1 min-w-0">
          {active && (
            <>
              <div className="mb-4">
                <h3 className="text-base font-bold text-ink-100">{active.name}</h3>
                <p className="text-sm text-ink-400 mt-1">{active.description}</p>
              </div>
              <div className="card p-6 space-y-5">
                {active.credential_fields.map((field) => (
                  <div key={field.name}>
                    <label className="block text-sm font-medium text-ink-300 mb-1.5">
                      {field.label}
                      {field.required && <span className="text-error-400 ml-0.5">*</span>}
                    </label>
                    <input
                      type={field.field_type === "password" ? "password" : "text"}
                      value={credentials[field.name] || ""}
                      onChange={(e) => updateCredential(field.name, e.target.value)}
                      placeholder={field.placeholder}
                      className="input"
                    />
                  </div>
                ))}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink-300 mb-1.5">Status</label>
                    <select value={status} onChange={(e) => setStatus(e.target.value)} className="input">
                      <option value="disabled">Disabled</option>
                      <option value="enabled">Enabled</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-300 mb-1.5">Priority</label>
                    <input
                      type="number"
                      min={1}
                      max={999}
                      value={priority}
                      onChange={(e) => setPriority(parseInt(e.target.value, 10) || 100)}
                      className="input"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={handleSave} disabled={saving} className="btn-primary">
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button onClick={handleTest} disabled={testing || !hasCredentials} className="btn-secondary">
                    {testing ? "Testing..." : "Test connection"}
                  </button>
                </div>
                {saveMsg && <p className="text-sm text-success-500">{saveMsg}</p>}
                {testResult === true && <p className="text-sm text-success-500">Connection successful</p>}
                {testResult === false && (
                  <p className="text-sm text-error-400">Connection failed — check your credentials</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceResolverSection() {
  const [modules, setModules] = useState<ScraperModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [installPath, setInstallPath] = useState("");
  const [installing, setInstalling] = useState(false);
  const [installMsg, setInstallMsg] = useState("");

  useEffect(() => {
    api
      .listScraperModules()
      .then(setModules)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleInstall = async () => {
    if (!installPath.trim()) return;
    setInstalling(true);
    setInstallMsg("");
    try {
      const result = await api.installScraperModule(installPath.trim());
      setModules((prev) => [
        ...prev,
        {
          module_id: result.module_id,
          name: result.name,
          version: result.version,
          description: result.description,
          scrapers: result.scrapers,
        },
      ]);
      setInstallPath("");
      setInstallMsg("Module installed successfully");
    } catch (err) {
      setInstallMsg(err instanceof Error ? err.message : "Install failed");
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstall = async (moduleId: string) => {
    try {
      await api.uninstallScraperModule(moduleId);
      setModules((prev) => prev.filter((m) => m.module_id !== moduleId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Uninstall failed");
    }
  };

  const handleToggle = async (key: string, enabled: boolean) => {
    try {
      const updated = await api.toggleScraper(key, enabled);
      setModules((prev) =>
        prev.map((m) => ({
          ...m,
          scrapers: m.scrapers.map((s) =>
            s.key === key ? { ...s, enabled: updated.enabled } : s
          ),
        }))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    }
  };

  if (loading) return <LoadingSpinner label="Loading source resolvers" />;
  if (error && modules.length === 0) return <ErrorState message={error} />;

  return (
    <div>
      <h2 className="text-lg font-bold text-ink-100 mb-1">Source Resolvers</h2>
      <p className="text-sm text-ink-400 mb-5">
        Installable scraper modules that discover torrent sources for cache checking.
      </p>

      {/* Install form */}
      <div className="card p-5 mb-6">
        <h3 className="text-sm font-semibold text-ink-200 mb-3">Install Module</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={installPath}
            onChange={(e) => setInstallPath(e.target.value)}
            placeholder="/scraper_modules/kondooit-scrapers-default"
            className="input flex-1"
          />
          <button
            onClick={handleInstall}
            disabled={installing || !installPath.trim()}
            className="btn-primary whitespace-nowrap"
          >
            {installing ? "Installing..." : "Install"}
          </button>
        </div>
        {installMsg && (
          <p className={`text-sm mt-2 ${installMsg.includes("failed") || installMsg.includes("Invalid") ? "text-error-400" : "text-success-500"}`}>
            {installMsg}
          </p>
        )}
      </div>

      {/* Installed modules */}
      {modules.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-ink-400">No scraper modules installed yet.</p>
          <p className="text-sm text-ink-500 mt-1">
            Install a module using the path to its directory in the container filesystem.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {modules.map((mod) => (
            <div key={mod.module_id} className="card p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-base font-bold text-ink-100">{mod.name}</h3>
                  <p className="text-sm text-ink-400 mt-0.5">{mod.description}</p>
                  <span className="text-xs text-ink-500 mt-1 inline-block">v{mod.version}</span>
                </div>
                <button
                  onClick={() => handleUninstall(mod.module_id)}
                  className="text-xs text-error-400 hover:text-error-300 transition-colors px-2 py-1 rounded hover:bg-error-400/10"
                >
                  Uninstall
                </button>
              </div>
              <div className="space-y-2">
                {mod.scrapers.map((scraper) => (
                  <div
                    key={scraper.key}
                    className="flex items-center justify-between p-3 rounded-lg bg-ink-900/50 border border-ink-800/50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-ink-200">{scraper.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-800/60 text-ink-500">
                        {scraper.category}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-800/60 text-ink-500">
                        tier {scraper.tier}
                      </span>
                    </div>
                    <button
                      onClick={() => handleToggle(scraper.key, !scraper.enabled)}
                      className={`relative w-10 h-5 rounded-full transition-colors ${
                        scraper.enabled ? "bg-brand-600" : "bg-ink-700"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                          scraper.enabled ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {error && modules.length > 0 && (
        <p className="text-sm text-error-400 mt-3">{error}</p>
      )}
    </div>
  );
}

export function ProvidersPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-ink-100 mb-8">Providers</h1>
      <div className="space-y-12">
        <MetadataProviderSection />
        <SourceProviderSection />
        <SourceResolverSection />
      </div>
    </div>
  );
}
