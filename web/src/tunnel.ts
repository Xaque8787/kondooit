/**
 * Tunnel transport -- loads the WASM runtime on demand and routes
 * API calls through the iroh tunnel when in remote mode.
 *
 * Local mode: this module is inert; isTunnelMode() returns false.
 * Remote mode: detected via a URL fragment (#base64payload) containing
 * the server endpoint ID, matching the connection URL format the server
 * generates.
 */

interface KondooitRuntime {
  endpoint_id(): string;
  secret_hex(): string;
  connect(endpoint_id: string): Promise<boolean>;
  ping(endpoint_id: string): Promise<string>;
  http_fetch(
    method: string,
    path: string,
    headers_json: string,
    body: string | undefined,
  ): Promise<string>;
}

interface WasmModule {
  default: () => Promise<void>;
  KondooitRuntime: {
    spawn(secret?: string): Promise<KondooitRuntime>;
  };
}

// ---------------------------------------------------------------------------
// Singleton state
// ---------------------------------------------------------------------------

let runtime: KondooitRuntime | null = null;
let serverEndpointId: string | null = null;
let connectionPromise: Promise<void> | null = null;
let tunnelModeActivated = false;

const SERVER_ID_KEY = "kondooit_tunnel_server_id";

// ---------------------------------------------------------------------------
// Bootstrap payload parsing (matches server's connection_url format)
// ---------------------------------------------------------------------------

function base64urlDecode(str: string): string {
  let b64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4 !== 0) b64 += "=";
  return atob(b64);
}

interface BootstrapPayload {
  v: number;
  endpoint_id: string;
}

function parseBootstrapPayload(): BootstrapPayload | null {
  const fragment = window.location.hash.slice(1);
  if (!fragment) return null;
  try {
    const json = base64urlDecode(fragment);
    const payload = JSON.parse(json) as BootstrapPayload;
    if (!payload.endpoint_id || typeof payload.endpoint_id !== "string") {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function captureServerIdFromFragment(): void {
  const payload = parseBootstrapPayload();
  if (payload) {
    sessionStorage.setItem(SERVER_ID_KEY, payload.endpoint_id);
    tunnelModeActivated = true;
  }
}

captureServerIdFromFragment();

export function isTunnelMode(): boolean {
  if (tunnelModeActivated) return true;
  if (sessionStorage.getItem(SERVER_ID_KEY)) {
    tunnelModeActivated = true;
    return true;
  }
  return false;
}

export function getTunnelServerId(): string | null {
  const payload = parseBootstrapPayload();
  if (payload) return payload.endpoint_id;
  return sessionStorage.getItem(SERVER_ID_KEY);
}

export type TunnelStatus =
  | { phase: "idle" }
  | { phase: "loading-wasm" }
  | { phase: "creating-endpoint" }
  | { phase: "connecting"; serverId: string }
  | { phase: "connected"; serverId: string; localId: string }
  | { phase: "error"; message: string };

type StatusCallback = (status: TunnelStatus) => void;

let statusCallback: StatusCallback | null = null;

export function onTunnelStatus(cb: StatusCallback) {
  statusCallback = cb;
}

function emitStatus(s: TunnelStatus) {
  statusCallback?.(s);
}

export async function initTunnel(serverId: string): Promise<void> {
  if (connectionPromise) return connectionPromise;

  connectionPromise = (async () => {
    try {
      emitStatus({ phase: "loading-wasm" });

      const wasmBase = import.meta.env.BASE_URL ?? "/";
      const wasm = (await import(
        /* @vite-ignore */ `${wasmBase}wasm/kondooit_runtime.js`
      )) as unknown as WasmModule;
      await wasm.default();

      emitStatus({ phase: "creating-endpoint" });

      const savedSecret = localStorage.getItem("kondooit_runtime_secret");
      runtime = await wasm.KondooitRuntime.spawn(savedSecret ?? undefined);
      localStorage.setItem("kondooit_runtime_secret", runtime.secret_hex());

      emitStatus({ phase: "connecting", serverId });

      serverEndpointId = serverId;
      tunnelModeActivated = true;
      await runtime.connect(serverId);

      emitStatus({
        phase: "connected",
        serverId,
        localId: runtime.endpoint_id(),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      emitStatus({ phase: "error", message: msg });
      connectionPromise = null;
      throw err;
    }
  })();

  return connectionPromise;
}

export function isConnected(): boolean {
  return runtime !== null && serverEndpointId !== null;
}

export async function tunnelFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  if (!runtime) {
    throw new Error("Tunnel not initialized");
  }

  const method = (options.method ?? "GET").toUpperCase();

  const headerPairs: [string, string][] = [];
  if (options.headers) {
    const h = options.headers as Record<string, string>;
    for (const [k, v] of Object.entries(h)) {
      headerPairs.push([k, v]);
    }
  }

  const body =
    typeof options.body === "string" ? options.body : undefined;

  const resultJson = await runtime.http_fetch(
    method,
    path,
    JSON.stringify(headerPairs),
    body,
  );

  const parsed = JSON.parse(resultJson) as {
    status: number;
    headers: Record<string, string>;
    body: string;
  };

  return new Response(parsed.body, {
    status: parsed.status,
    headers: parsed.headers,
  });
}
