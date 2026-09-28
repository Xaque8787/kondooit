//! wasm-bindgen wrapper -- exposes `KondooitRuntime` to JavaScript.

use tracing::level_filters::LevelFilter;
use tracing_subscriber_wasm::MakeConsoleWriter;
use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::future_to_promise;

use crate::{KondooitConnection, ALPN, STREAM_TYPE_HTTP};

// ---------------------------------------------------------------------------
// Module init
// ---------------------------------------------------------------------------

#[wasm_bindgen(start)]
fn start() {
    console_error_panic_hook::set_once();

    tracing_subscriber::fmt()
        .with_max_level(LevelFilter::INFO)
        .with_writer(
            MakeConsoleWriter::default().map_trace_level_to(tracing::Level::DEBUG),
        )
        .without_time()
        .with_ansi(false)
        .init();

    tracing::info!("kondooit-runtime WASM initialized");
}

// ---------------------------------------------------------------------------
// KondooitRuntime — the JS-facing API
// ---------------------------------------------------------------------------

#[wasm_bindgen]
pub struct KondooitRuntime {
    connection: KondooitConnection,
    secret_hex: String,
    /// Cached server endpoint ID after a successful connect().
    server_endpoint_id: Option<String>,
}

#[wasm_bindgen]
impl KondooitRuntime {
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
            server_endpoint_id: None,
        })
    }

    pub fn endpoint_id(&self) -> String {
        self.connection.endpoint().id().to_string()
    }

    pub fn secret_hex(&self) -> String {
        self.secret_hex.clone()
    }

    /// Connect to a remote Kondooit server by endpoint ID.
    /// Caches the server ID for subsequent http_fetch / ping calls.
    pub fn connect(&mut self, endpoint_id: String) -> js_sys::Promise {
        let ep = self.connection.endpoint().clone();
        let id_clone = endpoint_id.clone();
        // We can't borrow &mut self across async, so use a channel-like pattern.
        // Instead, we'll set server_endpoint_id before the async block.
        self.server_endpoint_id = Some(endpoint_id.clone());

        let connection = KondooitConnection::new(ep);
        future_to_promise(async move {
            let conn = connection.connect(&id_clone).await.map_err(js_err)?;
            conn.close(0u32.into(), b"ok");
            Ok(JsValue::TRUE)
        })
    }

    /// MVP test: open a control bidi stream, send "PING\n", return the response.
    pub fn ping(&self, endpoint_id: String) -> js_sys::Promise {
        let connection = KondooitConnection::new(self.connection.endpoint().clone());
        future_to_promise(async move {
            match connection.ping(&endpoint_id).await {
                Ok(response) => Ok(JsValue::from_str(&response)),
                Err(err) => Err(js_err(err).into()),
            }
        })
    }

    /// Send an HTTP request through the iroh tunnel and return the raw response.
    ///
    /// `method` — HTTP method (GET, POST, etc.)
    /// `path` — request path (e.g. "/auth/login")
    /// `headers_json` — JSON-encoded array of [key, value] pairs
    /// `body` — optional request body string
    ///
    /// Returns a JSON string: { "status": 200, "headers": {...}, "body": "..." }
    pub fn http_fetch(
        &self,
        method: String,
        path: String,
        headers_json: String,
        body: Option<String>,
    ) -> js_sys::Promise {
        let endpoint_id = self.server_endpoint_id.clone();
        let connection = KondooitConnection::new(self.connection.endpoint().clone());

        future_to_promise(async move {
            let server_id = endpoint_id
                .ok_or_else(|| js_err("not connected — call connect() first"))?;

            let conn = connection.connect(&server_id).await.map_err(js_err)?;

            let (mut send, mut recv) = conn
                .open_bi()
                .await
                .map_err(|e| js_err(format!("open_bi failed: {e}")))?;

            // Write HTTP stream-type prefix
            send.write_all(&[STREAM_TYPE_HTTP])
                .await
                .map_err(|e| js_err(format!("write prefix: {e}")))?;

            // Build a raw HTTP/1.1 request
            let body_bytes = body.as_deref().unwrap_or("");
            let mut request = format!("{method} {path} HTTP/1.1\r\nHost: localhost\r\n");

            // Parse custom headers
            if let Ok(pairs) = serde_json::from_str::<Vec<(String, String)>>(&headers_json) {
                for (k, v) in &pairs {
                    request.push_str(&format!("{k}: {v}\r\n"));
                }
            }

            if !body_bytes.is_empty() {
                request.push_str(&format!("Content-Length: {}\r\n", body_bytes.len()));
            }
            request.push_str("Connection: close\r\n\r\n");
            request.push_str(body_bytes);

            send.write_all(request.as_bytes())
                .await
                .map_err(|e| js_err(format!("write request: {e}")))?;
            send.finish()
                .map_err(|e| js_err(format!("finish: {e}")))?;

            // Read the full HTTP response
            let mut response_buf = Vec::new();
            let mut chunk = [0u8; 8192];
            while let Some(n) = recv
                .read(&mut chunk)
                .await
                .map_err(|e| js_err(format!("read: {e}")))?
            {
                response_buf.extend_from_slice(&chunk[..n]);
            }

            conn.close(0u32.into(), b"done");

            let raw = String::from_utf8_lossy(&response_buf).into_owned();

            // Parse the HTTP response into a structured JSON result
            let result = parse_http_response(&raw);
            Ok(JsValue::from_str(&result))
        })
    }
}

// ---------------------------------------------------------------------------
// HTTP response parsing
// ---------------------------------------------------------------------------

fn parse_http_response(raw: &str) -> String {
    // Split headers from body at the first \r\n\r\n
    let (header_section, body) = match raw.find("\r\n\r\n") {
        Some(pos) => (&raw[..pos], &raw[pos + 4..]),
        None => (raw, ""),
    };

    let mut lines = header_section.lines();

    // Parse status line
    let status: u16 = lines
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    // Parse headers into a JSON object
    let mut headers = serde_json::Map::new();
    for line in lines {
        if let Some((key, value)) = line.split_once(':') {
            headers.insert(
                key.trim().to_lowercase(),
                serde_json::Value::String(value.trim().to_string()),
            );
        }
    }

    let result = serde_json::json!({
        "status": status,
        "headers": headers,
        "body": body,
    });

    result.to_string()
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn js_err(err: impl std::fmt::Display) -> JsError {
    JsError::new(&err.to_string())
}

fn hex_encode(bytes: &[u8]) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::with_capacity(bytes.len() * 2), |mut s, b| {
        let _ = write!(s, "{b:02x}");
        s
    })
}
