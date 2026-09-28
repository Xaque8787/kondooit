// Kondooit browser runtime — loads WASM, parses bootstrap fragment, connects.
//
// wasm-bindgen `--target web` emits an ES module + a default `init()` that
// fetches and instantiates the .wasm file.
import init, { KondooitRuntime } from "./wasm/kondooit_runtime.js";

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const steps = {
  loading:    document.getElementById("step-loading"),
  endpoint:   document.getElementById("step-endpoint"),
  connecting: document.getElementById("step-connecting"),
  connected:  document.getElementById("step-connected"),
};

const $infoSection    = document.getElementById("info-section");
const $pingSection    = document.getElementById("ping-section");
const $errorSection   = document.getElementById("error-section");
const $errorMessage   = document.getElementById("error-message");
const $localId        = document.getElementById("local-endpoint-id");
const $serverId       = document.getElementById("server-endpoint-id");
const $connStatus     = document.getElementById("connection-status");
const $pingBtn        = document.getElementById("ping-btn");
const $pingResult     = document.getElementById("ping-result");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setStep(name, status) {
  const el = steps[name];
  if (el) el.dataset.status = status;
}

function showError(msg) {
  $errorMessage.textContent = msg;
  $errorSection.classList.remove("hidden");
}

/** Base64url decode (RFC 4648 §5, no padding required). */
function base64urlDecode(str) {
  // Convert base64url → standard base64
  let b64 = str.replace(/-/g, "+").replace(/_/g, "/");
  // Pad if needed
  while (b64.length % 4 !== 0) b64 += "=";
  return atob(b64);
}

/**
 * Parse the URL fragment for the bootstrap payload.
 * Format: #base64url-encoded-json
 * Payload: { "v": 1, "endpoint_id": "..." }
 */
function parseBootstrapPayload() {
  const fragment = window.location.hash.slice(1); // remove leading '#'
  if (!fragment) return null;

  try {
    const json = base64urlDecode(fragment);
    const payload = JSON.parse(json);

    if (payload.v !== 1) {
      console.warn("Unknown bootstrap payload version:", payload.v);
    }
    if (!payload.endpoint_id || typeof payload.endpoint_id !== "string") {
      throw new Error("Missing or invalid endpoint_id in bootstrap payload");
    }
    return payload;
  } catch (err) {
    console.error("Failed to parse bootstrap payload:", err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Persistent identity
// ---------------------------------------------------------------------------

const SECRET_STORAGE_KEY = "kondooit:secret";

// ---------------------------------------------------------------------------
// Main flow
// ---------------------------------------------------------------------------

async function main() {
  // Step 1: Load WASM
  setStep("loading", "active");
  try {
    await init();
    setStep("loading", "done");
  } catch (err) {
    setStep("loading", "error");
    showError(`Failed to load WASM runtime: ${err}`);
    console.error(err);
    return;
  }

  // Step 2: Create iroh endpoint
  setStep("endpoint", "active");
  let runtime;
  try {
    // null when absent → wasm sees None → generates a fresh key.
    runtime = await KondooitRuntime.spawn(
      localStorage.getItem(SECRET_STORAGE_KEY),
    );
    // Persist (idempotent if it already existed; stores the new one otherwise).
    localStorage.setItem(SECRET_STORAGE_KEY, runtime.secret_hex());

    $localId.textContent = runtime.endpoint_id();
    $localId.addEventListener("click", () =>
      getSelection().selectAllChildren($localId),
    );

    setStep("endpoint", "done");
  } catch (err) {
    setStep("endpoint", "error");
    showError(`Failed to create endpoint: ${err}`);
    console.error(err);
    return;
  }

  // Step 3: Parse bootstrap payload and connect
  const payload = parseBootstrapPayload();

  if (!payload) {
    // No server to connect to — show endpoint info and wait
    setStep("connecting", "skipped");
    setStep("connected", "skipped");
    $infoSection.classList.remove("hidden");
    $connStatus.textContent = "No server specified (add #payload to URL)";
    $connStatus.classList.add("warning");
    return;
  }

  const serverEndpointId = payload.endpoint_id;
  $serverId.textContent = serverEndpointId;

  setStep("connecting", "active");
  $infoSection.classList.remove("hidden");
  $connStatus.textContent = "Connecting…";

  try {
    await runtime.connect(serverEndpointId);
    setStep("connecting", "done");
    setStep("connected", "done");
    $connStatus.textContent = "Connected ✓";
    $connStatus.classList.add("success");

    // Show ping section for MVP testing
    $pingSection.classList.remove("hidden");
    setupPing(runtime, serverEndpointId);
  } catch (err) {
    setStep("connecting", "error");
    $connStatus.textContent = "Failed";
    $connStatus.classList.add("error");
    showError(`Connection failed: ${err}`);
    console.error(err);
  }
}

// ---------------------------------------------------------------------------
// Ping (MVP test)
// ---------------------------------------------------------------------------

function setupPing(runtime, serverEndpointId) {
  $pingBtn.addEventListener("click", async () => {
    $pingBtn.disabled = true;
    $pingResult.textContent = "Sending PING…";
    $pingResult.className = "mono";

    try {
      const response = await runtime.ping(serverEndpointId);
      $pingResult.textContent = `Response: ${response.trim()}`;
      $pingResult.classList.add("success");
    } catch (err) {
      $pingResult.textContent = `Error: ${err}`;
      $pingResult.classList.add("error");
      console.error(err);
    } finally {
      $pingBtn.disabled = false;
    }
  });
}

// ---------------------------------------------------------------------------
// Go
// ---------------------------------------------------------------------------

main().catch((err) => {
  showError(`Unexpected error: ${err}`);
  console.error(err);
});
