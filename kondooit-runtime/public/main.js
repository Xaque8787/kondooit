// Kondooit browser runtime — connects via iroh, authenticates, browses catalog.
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
const $loginSection   = document.getElementById("login-section");
const $userSection    = document.getElementById("user-section");
const $catalogSection = document.getElementById("catalog-section");
const $detailSection  = document.getElementById("detail-section");
const $errorSection   = document.getElementById("error-section");
const $errorMessage   = document.getElementById("error-message");
const $localId        = document.getElementById("local-endpoint-id");
const $serverId       = document.getElementById("server-endpoint-id");
const $connStatus     = document.getElementById("connection-status");
const $pingBtn        = document.getElementById("ping-btn");
const $pingResult     = document.getElementById("ping-result");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let runtime = null;
let serverEndpointId = null;
let authToken = null;

const TOKEN_KEY = "kondooit:token";
const SECRET_STORAGE_KEY = "kondooit:secret";

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

function base64urlDecode(str) {
  let b64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4 !== 0) b64 += "=";
  return atob(b64);
}

function parseBootstrapPayload() {
  const fragment = window.location.hash.slice(1);
  if (!fragment) return null;
  try {
    const json = base64urlDecode(fragment);
    const payload = JSON.parse(json);
    if (!payload.endpoint_id || typeof payload.endpoint_id !== "string") {
      throw new Error("Missing endpoint_id in bootstrap payload");
    }
    return payload;
  } catch (err) {
    console.error("Failed to parse bootstrap payload:", err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Tunnel HTTP helper
// ---------------------------------------------------------------------------

async function tunnelFetch(method, path, { headers = {}, body = null } = {}) {
  const headerPairs = Object.entries(headers);
  if (authToken) {
    headerPairs.push(["Authorization", `Bearer ${authToken}`]);
  }
  if (body && !headerPairs.some(([k]) => k.toLowerCase() === "content-type")) {
    headerPairs.push(["Content-Type", "application/json"]);
  }

  console.log(`[tunnelFetch] ${method} ${path}`);

  if (typeof runtime.http_fetch !== "function") {
    throw new Error("WASM runtime does not have http_fetch — the deployed WASM may be outdated. Redeploy the browser runtime.");
  }

  let rawJson;
  try {
    rawJson = await runtime.http_fetch(
      method,
      path,
      JSON.stringify(headerPairs),
      body || null,
    );
  } catch (err) {
    console.error(`[tunnelFetch] http_fetch threw:`, err);
    throw err;
  }

  console.log(`[tunnelFetch] raw response (first 200 chars):`, rawJson?.slice?.(0, 200));

  const parsed = JSON.parse(rawJson);
  let responseBody = parsed.body || "";

  // Try parsing body as JSON
  try {
    parsed.json = JSON.parse(responseBody);
  } catch {
    parsed.json = null;
  }

  console.log(`[tunnelFetch] ${method} ${path} => status=${parsed.status}`);
  return parsed;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function setupLogin() {
  $loginSection.classList.remove("hidden");

  const form = document.getElementById("login-form");
  const $loginError = document.getElementById("login-error");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    const btn = document.getElementById("login-btn");

    $loginError.classList.add("hidden");
    btn.disabled = true;
    btn.textContent = "Signing in...";

    try {
      const resp = await tunnelFetch("POST", "/auth/login", {
        body: JSON.stringify({ username, password }),
      });

      if (resp.status === 200 && resp.json?.access_token) {
        authToken = resp.json.access_token;
        localStorage.setItem(TOKEN_KEY, authToken);
        $loginSection.classList.add("hidden");
        await onAuthenticated();
      } else {
        const detail = resp.json?.detail || `Login failed (${resp.status})`;
        $loginError.textContent = detail;
        $loginError.classList.remove("hidden");
      }
    } catch (err) {
      $loginError.textContent = `Connection error: ${err}`;
      $loginError.classList.remove("hidden");
      console.error(err);
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign In";
    }
  });
}

async function tryRestoredToken() {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (!saved) return false;

  authToken = saved;
  try {
    const resp = await tunnelFetch("GET", "/auth/me");
    if (resp.status === 200 && resp.json?.username) {
      return true;
    }
  } catch {
    // token invalid or expired
  }
  authToken = null;
  localStorage.removeItem(TOKEN_KEY);
  return false;
}

async function onAuthenticated() {
  // Fetch user info
  const me = await tunnelFetch("GET", "/auth/me");
  if (me.status === 200 && me.json) {
    const user = me.json;
    document.getElementById("user-name").textContent = user.username;
    document.getElementById("user-role").textContent = user.role;
    const avatar = document.getElementById("user-avatar");
    avatar.textContent = user.username[0].toUpperCase();
    $userSection.classList.remove("hidden");
  }

  // Setup logout
  document.getElementById("logout-btn").addEventListener("click", () => {
    authToken = null;
    localStorage.removeItem(TOKEN_KEY);
    $userSection.classList.add("hidden");
    $catalogSection.classList.add("hidden");
    $detailSection.classList.add("hidden");
    $loginSection.classList.remove("hidden");
  });

  // Show catalog
  $catalogSection.classList.remove("hidden");
  setupCatalogTabs();
  loadCatalog("movies");
}

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

let currentTab = "movies";

function setupCatalogTabs() {
  document.querySelectorAll(".catalog-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".catalog-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      currentTab = tab.dataset.tab;
      loadCatalog(currentTab);
    });
  });
}

async function loadCatalog(tab) {
  const $content = document.getElementById("catalog-content");
  const $empty = document.getElementById("catalog-empty");
  const $loading = document.getElementById("catalog-loading");

  $content.innerHTML = "";
  $empty.classList.add("hidden");
  $loading.classList.remove("hidden");
  $detailSection.classList.add("hidden");

  try {
    let items = [];

    if (tab === "movies") {
      const resp = await tunnelFetch("GET", "/catalog/movies?limit=50");
      if (resp.status === 200 && resp.json) items = resp.json;
    } else if (tab === "series") {
      const resp = await tunnelFetch("GET", "/catalog/series?limit=50");
      if (resp.status === 200 && resp.json) items = resp.json;
    } else if (tab === "discover") {
      const resp = await tunnelFetch("GET", "/discovery/landing");
      if (resp.status === 200 && resp.json) {
        // Flatten discovery sections into items
        for (const section of resp.json) {
          for (const m of section.movies || []) {
            items.push({ ...m, _type: "discovered_movie" });
          }
          for (const s of section.series || []) {
            items.push({ ...s, _type: "discovered_series" });
          }
        }
      }
    }

    $loading.classList.add("hidden");

    if (items.length === 0) {
      $empty.classList.remove("hidden");
      return;
    }

    for (const item of items) {
      $content.appendChild(createCard(item, tab));
    }
  } catch (err) {
    $loading.classList.add("hidden");
    $content.innerHTML = `<div class="catalog-error">Failed to load: ${err}</div>`;
    console.error(err);
  }
}

function createCard(item, tab) {
  const card = document.createElement("div");
  card.className = "content-card";

  const title = item.title || "Untitled";
  const poster = item.poster_path
    ? `https://image.tmdb.org/t/p/w300${item.poster_path}`
    : null;
  const year = item.release_date?.slice(0, 4)
    || item.first_air_date?.slice(0, 4)
    || "";
  const rating = item.vote_average ? item.vote_average.toFixed(1) : "";

  card.innerHTML = `
    <div class="card-poster">
      ${poster ? `<img src="${poster}" alt="${title}" loading="lazy" />` : `<div class="card-no-poster">${title[0]}</div>`}
      ${rating ? `<span class="card-rating">${rating}</span>` : ""}
    </div>
    <div class="card-info">
      <div class="card-title">${title}</div>
      ${year ? `<div class="card-year">${year}</div>` : ""}
    </div>
  `;

  card.addEventListener("click", () => showDetail(item, tab));
  return card;
}

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

async function showDetail(item, tab) {
  $detailSection.classList.remove("hidden");
  $catalogSection.classList.add("hidden");

  const $title = document.getElementById("detail-title");
  const $year = document.getElementById("detail-year");
  const $runtime = document.getElementById("detail-runtime");
  const $rating = document.getElementById("detail-rating");
  const $overview = document.getElementById("detail-overview");
  const $poster = document.getElementById("detail-poster");
  const $backdrop = document.getElementById("detail-backdrop");
  const $genres = document.getElementById("detail-genres");
  const $actions = document.getElementById("detail-actions");

  $title.textContent = item.title || "Untitled";
  $year.textContent = item.release_date?.slice(0, 4) || item.first_air_date?.slice(0, 4) || "";
  $runtime.textContent = item.runtime_minutes ? `${item.runtime_minutes} min` : "";
  $rating.textContent = item.vote_average ? `${item.vote_average.toFixed(1)} / 10` : "";
  $overview.textContent = item.overview || "No overview available.";

  if (item.poster_path) {
    $poster.src = `https://image.tmdb.org/t/p/w300${item.poster_path}`;
    $poster.classList.remove("hidden");
  } else {
    $poster.classList.add("hidden");
  }

  if (item.backdrop_path) {
    $backdrop.style.backgroundImage = `url(https://image.tmdb.org/t/p/w780${item.backdrop_path})`;
  } else {
    $backdrop.style.backgroundImage = "none";
  }

  // Genres
  $genres.innerHTML = "";
  if (item.genres) {
    for (const g of item.genres) {
      const chip = document.createElement("span");
      chip.className = "genre-chip";
      chip.textContent = g.name;
      $genres.appendChild(chip);
    }
  }

  // Actions -- attempt source search / playback
  $actions.innerHTML = "";

  // For catalog items, try to search sources
  if (item.id && (tab === "movies" || tab === "series")) {
    const searchBtn = document.createElement("button");
    searchBtn.textContent = "Search Sources";
    searchBtn.className = "btn-primary";
    searchBtn.addEventListener("click", () => searchSources(item, tab));
    $actions.appendChild(searchBtn);
  }

  // For discovered items, show "add to catalog" info
  if (item._type === "discovered_movie" || item._type === "discovered_series") {
    const note = document.createElement("p");
    note.className = "detail-note";
    note.textContent = "This content was found via discovery. Add it to your catalog from the main server to search for sources.";
    $actions.appendChild(note);
  }

  // Back button
  document.getElementById("detail-back").onclick = () => {
    $detailSection.classList.add("hidden");
    $catalogSection.classList.remove("hidden");
  };
}

async function searchSources(item, tab) {
  const $actions = document.getElementById("detail-actions");
  const contentType = tab === "movies" ? "movie" : "series";

  $actions.innerHTML = `<div class="source-loading"><div class="spinner"></div> Searching for sources...</div>`;

  try {
    const body = {
      title: item.title,
      content_type: contentType,
      tmdb_id: item.tmdb_id || undefined,
      year: item.release_date ? parseInt(item.release_date.slice(0, 4), 10) : undefined,
    };

    const resp = await tunnelFetch("POST", "/source-providers/search", {
      body: JSON.stringify(body),
    });

    if (resp.status === 200 && resp.json && resp.json.length > 0) {
      $actions.innerHTML = `<h3 class="sources-title">${resp.json.length} source(s) found</h3>`;
      for (const source of resp.json) {
        const row = document.createElement("div");
        row.className = "source-row";

        const sizeMB = source.size_bytes > 0
          ? (source.size_bytes >= 1073741824
            ? (source.size_bytes / 1073741824).toFixed(1) + " GB"
            : (source.size_bytes / 1048576).toFixed(0) + " MB")
          : "";
        const quality = source.quality || "";
        const codec = source.codec || "";
        const provider = source.provider_key || "";
        const sourceType = source.source_type || "";
        const compat = source.playback_compatibility || "";

        let badges = "";
        if (quality) badges += `<span class="source-badge quality">${quality}</span>`;
        if (codec) badges += `<span class="source-badge codec">${codec}</span>`;
        if (sourceType === "cached_torrent") badges += `<span class="source-badge cached">Cached</span>`;
        if (sourceType === "direct") badges += `<span class="source-badge direct">Direct</span>`;
        if (sourceType === "in_library") badges += `<span class="source-badge cached">In Library</span>`;
        if (compat === "direct_play") badges += `<span class="source-badge compat-good">Direct Play</span>`;
        else if (compat === "remux") badges += `<span class="source-badge compat-ok">Remux</span>`;

        row.innerHTML = `
          <div class="source-info">
            <span class="source-name">${source.filename || "Source"}</span>
            <div class="source-badges">${badges}</div>
            <span class="source-detail">${sizeMB} ${provider ? "via " + provider : ""}</span>
          </div>
        `;

        // Determine what action buttons to show
        const btnContainer = document.createElement("div");
        btnContainer.className = "source-actions";

        if (source.stream_id) {
          // Already has a stream handle — can attempt play
          const playBtn = document.createElement("button");
          playBtn.className = "btn-small btn-primary";
          playBtn.textContent = "Play";
          playBtn.addEventListener("click", () => attemptPlayback(source.stream_id, source.filename));
          btnContainer.appendChild(playBtn);
        } else if (source.info_hash) {
          // Needs resolve first
          const resolveBtn = document.createElement("button");
          resolveBtn.className = "btn-small btn-primary";
          resolveBtn.textContent = "Stream";
          resolveBtn.addEventListener("click", async () => {
            resolveBtn.disabled = true;
            resolveBtn.textContent = "Resolving...";
            try {
              const res = await tunnelFetch("POST", "/source-providers/resolve", {
                body: JSON.stringify({
                  info_hash: source.info_hash,
                  provider_key: source.provider_key,
                }),
              });
              if (res.status === 200 && res.json?.success && res.json.stream_id) {
                resolveBtn.textContent = "Play";
                resolveBtn.disabled = false;
                resolveBtn.onclick = () => attemptPlayback(res.json.stream_id, source.filename);
              } else {
                resolveBtn.textContent = "Failed";
                resolveBtn.disabled = true;
              }
            } catch (err) {
              resolveBtn.textContent = "Error";
              console.error(err);
            }
          });
          btnContainer.appendChild(resolveBtn);
        }

        row.appendChild(btnContainer);
        $actions.appendChild(row);
      }
    } else {
      $actions.innerHTML = `<p class="detail-note">No sources found. Configure source providers on your server.</p>`;
    }
  } catch (err) {
    $actions.innerHTML = `<p class="detail-note error">Source search failed: ${err}</p>`;
    console.error(err);
  }
}

async function attemptPlayback(streamId, filename) {
  const $actions = document.getElementById("detail-actions");

  // Show loading state
  const statusEl = document.createElement("div");
  statusEl.className = "source-loading";
  statusEl.innerHTML = `<div class="spinner"></div> Getting playback URL...`;
  $actions.appendChild(statusEl);

  try {
    // Ask the server for the direct upstream URL
    const resp = await tunnelFetch("GET", `/streams/${streamId}/direct-url`);

    if (resp.status === 200 && resp.json?.url) {
      const directUrl = resp.json.url;
      const hasAuth = resp.json.has_auth;

      statusEl.remove();

      if (hasAuth) {
        // Source requires authentication — can't play directly from remote
        const note = document.createElement("p");
        note.className = "detail-note warning";
        note.textContent = "This source requires authentication and cannot be played directly from a remote connection. Use the main server for playback.";
        $actions.appendChild(note);
        return;
      }

      // Launch the video player with the direct URL
      showPlayer(directUrl, filename || "Video");
    } else {
      statusEl.innerHTML = `<p class="detail-note error">Could not get playback URL (${resp.status})</p>`;
    }
  } catch (err) {
    statusEl.innerHTML = `<p class="detail-note error">Playback failed: ${err}</p>`;
    console.error(err);
  }
}

function showPlayer(url, title) {
  // Hide other sections, show a full-screen video player
  $catalogSection.classList.add("hidden");
  $detailSection.classList.add("hidden");

  let $player = document.getElementById("player-section");
  if (!$player) {
    $player = document.createElement("section");
    $player.id = "player-section";
    document.querySelector("main").appendChild($player);
  }

  $player.innerHTML = `
    <div class="player-card">
      <div class="player-header">
        <button id="player-back" class="btn-secondary btn-small">Back</button>
        <span class="player-title">${title}</span>
      </div>
      <video
        id="player-video"
        controls
        autoplay
        playsinline
        class="player-video"
      >
        <source src="${url}" />
        Your browser does not support video playback.
      </video>
      <div id="player-error" class="hidden"></div>
    </div>
  `;
  $player.classList.remove("hidden");

  const video = document.getElementById("player-video");
  const errorEl = document.getElementById("player-error");

  video.addEventListener("error", () => {
    const code = video.error?.code;
    const msg = video.error?.message || "Unknown error";
    errorEl.textContent = `Playback error (code ${code}): ${msg}. The source URL may have expired or the format may not be supported by your browser.`;
    errorEl.className = "player-error-msg";
  });

  document.getElementById("player-back").addEventListener("click", () => {
    video.pause();
    video.src = "";
    $player.classList.add("hidden");
    $detailSection.classList.remove("hidden");
  });
}

// ---------------------------------------------------------------------------
// Ping (MVP test)
// ---------------------------------------------------------------------------

function setupPing(rt, sid) {
  $pingBtn.addEventListener("click", async () => {
    $pingBtn.disabled = true;
    $pingResult.textContent = "Sending PING...";
    $pingResult.className = "mono";

    try {
      const response = await rt.ping(sid);
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
    return;
  }

  // Step 2: Create iroh endpoint
  setStep("endpoint", "active");
  try {
    runtime = await KondooitRuntime.spawn(
      localStorage.getItem(SECRET_STORAGE_KEY),
    );
    localStorage.setItem(SECRET_STORAGE_KEY, runtime.secret_hex());
    $localId.textContent = runtime.endpoint_id();
    setStep("endpoint", "done");
  } catch (err) {
    setStep("endpoint", "error");
    showError(`Failed to create endpoint: ${err}`);
    return;
  }

  // Step 3: Parse bootstrap payload and connect
  const payload = parseBootstrapPayload();

  if (!payload) {
    setStep("connecting", "skipped");
    setStep("connected", "skipped");
    $infoSection.classList.remove("hidden");
    $connStatus.textContent = "No server specified (add #payload to URL)";
    $connStatus.classList.add("warning");
    return;
  }

  serverEndpointId = payload.endpoint_id;
  $serverId.textContent = serverEndpointId;

  setStep("connecting", "active");
  $infoSection.classList.remove("hidden");
  $connStatus.textContent = "Connecting...";

  try {
    await runtime.connect(serverEndpointId);
    setStep("connecting", "done");
    setStep("connected", "done");
    $connStatus.textContent = "Connected";
    $connStatus.classList.add("success");

    // Show ping for testing
    $pingSection.classList.remove("hidden");
    setupPing(runtime, serverEndpointId);

    // Try restoring a previous session
    const restored = await tryRestoredToken();
    if (restored) {
      await onAuthenticated();
    } else {
      setupLogin();
    }
  } catch (err) {
    setStep("connecting", "error");
    $connStatus.textContent = "Failed";
    $connStatus.classList.add("error");
    showError(`Connection failed: ${err}`);
  }
}

main().catch((err) => {
  showError(`Unexpected error: ${err}`);
  console.error(err);
});
