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

  const rawJson = await runtime.http_fetch(
    method,
    path,
    JSON.stringify(headerPairs),
    body || null,
  );

  const parsed = JSON.parse(rawJson);
  let responseBody = parsed.body || "";

  // Try parsing body as JSON
  try {
    parsed.json = JSON.parse(responseBody);
  } catch {
    parsed.json = null;
  }

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
    const resp = await tunnelFetch(
      "GET",
      `/source-providers/search?content_type=${contentType}&content_id=${item.id}&title=${encodeURIComponent(item.title)}&year=${item.release_date?.slice(0, 4) || ""}`,
    );

    if (resp.status === 200 && resp.json && resp.json.length > 0) {
      $actions.innerHTML = `<h3 class="sources-title">${resp.json.length} source(s) found</h3>`;
      for (const source of resp.json) {
        const row = document.createElement("div");
        row.className = "source-row";
        row.innerHTML = `
          <div class="source-info">
            <span class="source-name">${source.title || source.name || "Source"}</span>
            <span class="source-detail">${source.quality || ""} ${source.size_display || ""}</span>
          </div>
          <button class="btn-small btn-primary">Play</button>
        `;
        row.querySelector("button").addEventListener("click", () => {
          attemptPlayback(source);
        });
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

async function attemptPlayback(source) {
  const $actions = document.getElementById("detail-actions");
  const note = document.createElement("p");
  note.className = "detail-note";
  note.textContent = "Playback through the remote tunnel is not yet supported. Use the main server interface for playback.";
  $actions.appendChild(note);
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
