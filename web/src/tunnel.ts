/**
 * Tunnel transport — loads the WASM runtime on demand and routes
 * API calls through the iroh tunnel when in remote mode.
 *
 * Local mode: this module is never loaded (tree-shaken away).
 * Remote mode: detected via ?tunnel=<server_endpoint_id> in the URL.
 */

// The WASM module is loaded dynamically at runtime from /wasm/
// (placed there by the deployment build). These types mirror the
// wasm-bindgen interface from kondooit-runtime/src/wasm.rs.
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

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function isTunnelMode(): boolean {
  if (tunnelModeActivated) return true;
  const has = new URLSearchParams(window.location.search).has("tunnel");
  if (has) tunnelModeActivated = true;
  return has;
}

export function getTunnelServerIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("tunnel");
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

/**
 * Perform an API request through the iroh tunnel.
 * Returns a Response-like object compatible with the fetch API subset
 * that api.ts uses.
 */
export async function tunnelFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  if (!runtime) {
    throw new Error("Tunnel not initialized — call initTunnel() first");
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
