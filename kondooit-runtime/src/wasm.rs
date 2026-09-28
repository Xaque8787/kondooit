//! wasm-bindgen wrapper — exposes `KondooitRuntime` to JavaScript.
//!
//! Structure mirrors the `browser-echo` / `wasm-gui` examples from iroh-examples:
//! a `#[wasm_bindgen(start)]` init hook plus an exported struct that JS drives.
//!
//! Browsers cannot open raw UDP/QUIC sockets, so this endpoint reaches peers
//! exclusively over a **relay** (the iroh `N0` preset wires up the n0 relays).
//! All connections are end-to-end encrypted regardless.

use tracing::level_filters::LevelFilter;
use tracing_subscriber_wasm::MakeConsoleWriter;
use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::future_to_promise;

use crate::{KondooitConnection, ALPN};

// ---------------------------------------------------------------------------
// Module init — runs once when the WASM module is loaded
// ---------------------------------------------------------------------------

/// Runs automatically when the WASM module is instantiated in the browser.
/// Sets up panic hooks and tracing → browser console.
#[wasm_bindgen(start)]
fn start() {
    // Readable panics in the console instead of an opaque wasm trap.
    console_error_panic_hook::set_once();

    // Route `tracing` (including iroh's internal logs) to the browser console.
    tracing_subscriber::fmt()
        .with_max_level(LevelFilter::INFO)
        .with_writer(
            // Map TRACE down so the browser doesn't attach a JS backtrace to every line.
            MakeConsoleWriter::default().map_trace_level_to(tracing::Level::DEBUG),
        )
        .without_time() // wall-clock time isn't available the usual way in wasm
        .with_ansi(false)
        .init();

    tracing::info!("kondooit-runtime WASM initialized");
}

// ---------------------------------------------------------------------------
// KondooitRuntime — the JS-facing API
// ---------------------------------------------------------------------------

/// A Kondooit runtime running in the browser, backed by an iroh endpoint.
#[wasm_bindgen]
pub struct KondooitRuntime {
    connection: KondooitConnection,
    /// Hex-encoded secret key so JS can persist it (localStorage) for a stable
    /// identity across reloads.
    secret_hex: String,
}

#[wasm_bindgen]
impl KondooitRuntime {
    /// Spawn a new iroh endpoint (the browser's Kondooit runtime).
    ///
    /// `secret` is an optional hex-encoded iroh secret key. Pass the one persisted
    /// from a previous session to keep a stable endpoint ID; pass `null`/`undefined`
    /// to generate a fresh identity (then read it back via `secret_hex()`).
    pub async fn spawn(secret: Option<String>) -> Result<KondooitRuntime, JsError> {
        let secret_key = match secret
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty())
        {
            Some(hex) => hex.parse::<iroh::SecretKey>().map_err(js_err)?,
            None => iroh::SecretKey::generate(),
        };

        let secret_hex = hex_encode(&secret_key.to_bytes());

        let endpoint = iroh::Endpoint::builder(iroh::endpoint::presets::N0)
            .secret_key(secret_key)
            .alpns(vec![ALPN.to_vec()])
            .bind()
            .await
            .map_err(js_err)?;

        tracing::info!(id = %endpoint.id(), "endpoint bound");

        Ok(KondooitRuntime {
            connection: KondooitConnection::new(endpoint),
            secret_hex,
        })
    }

    /// The endpoint's ID (its public key, hex-encoded).
    /// Available immediately after `spawn` — derived from the secret key,
    /// not from any relay connection.
    pub fn endpoint_id(&self) -> String {
        self.connection.endpoint().id().to_string()
    }

    /// The endpoint's secret key, hex-encoded — persist this to reuse the same
    /// identity next time. Treat it like a private key.
    pub fn secret_hex(&self) -> String {
        self.secret_hex.clone()
    }

    /// Connect to a remote Kondooit server by endpoint ID.
    ///
    /// Returns a `Promise<true>` — resolves on success, rejects on failure.
    /// The endpoint ID is the server sidecar's iroh public key (hex string).
    pub fn connect(&self, endpoint_id: String) -> js_sys::Promise {
        // Clone the connection's endpoint so the future is 'static (can't
        // borrow &self across an await in an exported wasm_bindgen method).
        let connection = KondooitConnection::new(self.connection.endpoint().clone());
        future_to_promise(async move {
            let conn = connection.connect(&endpoint_id).await.map_err(js_err)?;
            // For now, just confirm the connection succeeded and close cleanly.
            conn.close(0u32.into(), b"ok");
            Ok(JsValue::TRUE)
        })
    }

    /// MVP test: open a bidi stream, send "PING\n", return the response.
    ///
    /// Returns a `Promise<string>` that resolves with the server's reply.
    pub fn ping(&self, endpoint_id: String) -> js_sys::Promise {
        let connection = KondooitConnection::new(self.connection.endpoint().clone());
        future_to_promise(async move {
            match connection.ping(&endpoint_id).await {
                Ok(response) => Ok(JsValue::from_str(&response)),
                Err(err) => Err(js_err(err).into()),
            }
        })
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Wrap any `Display` error as a `JsError` for the JS boundary.
fn js_err(err: impl std::fmt::Display) -> JsError {
    JsError::new(&err.to_string())
}

/// Lowercase hex encoding (matches the format iroh CLIs use for secret keys).
fn hex_encode(bytes: &[u8]) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::with_capacity(bytes.len() * 2), |mut s, b| {
        let _ = write!(s, "{b:02x}");
        s
    })
}
