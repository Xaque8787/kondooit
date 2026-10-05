//! wasm-bindgen wrapper -- exposes `KondooitRuntime` to JavaScript.

use std::cell::RefCell;
use std::rc::Rc;

use tracing::level_filters::LevelFilter;
use tracing_subscriber_wasm::MakeConsoleWriter;
use wasm_bindgen::prelude::*;
use wasm_bindgen_futures::future_to_promise;

use crate::{KondooitConnection, ALPN, STREAM_TYPE_CONTROL, STREAM_TYPE_HTTP};
use base64::Engine;

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
// Shared persistent connection (single-threaded WASM — RefCell is fine)
// ---------------------------------------------------------------------------

type SharedConn = Rc<RefCell<Option<iroh::endpoint::Connection>>>;

// ---------------------------------------------------------------------------
// KondooitRuntime — the JS-facing API
// ---------------------------------------------------------------------------

#[wasm_bindgen]
pub struct KondooitRuntime {
    endpoint: iroh::Endpoint,
    secret_hex: String,
    server_endpoint_id: Option<String>,
    persistent_conn: SharedConn,
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
            endpoint,
            secret_hex,
            server_endpoint_id: None,
            persistent_conn: Rc::new(RefCell::new(None)),
        })
    }

    pub fn endpoint_id(&self) -> String {
        self.endpoint.id().to_string()
    }

    pub fn secret_hex(&self) -> String {
        self.secret_hex.clone()
    }

    /// Connect to a remote Kondooit server by endpoint ID.
    /// Establishes a persistent connection reused by ping() and http_fetch().
    pub fn connect(&mut self, endpoint_id: String) -> js_sys::Promise {
        self.server_endpoint_id = Some(endpoint_id.clone());

        let ep = self.endpoint.clone();
        let persistent = self.persistent_conn.clone();

        future_to_promise(async move {
            tracing::info!("connect: establishing persistent connection");
            let helper = KondooitConnection::new(ep);
            let conn = helper.connect(&endpoint_id).await.map_err(js_err)?;
            tracing::info!("connect: persistent connection established");

            *persistent.borrow_mut() = Some(conn);
            Ok(JsValue::TRUE)
        })
    }

    /// MVP test: open a control bidi stream, send "PING\n", return the response.
    pub fn ping(&self, _endpoint_id: String) -> js_sys::Promise {
        let persistent = self.persistent_conn.clone();
        let endpoint = self.endpoint.clone();
        let server_id = self.server_endpoint_id.clone();

        future_to_promise(async move {
            let conn = get_or_reconnect(&persistent, &endpoint, server_id.as_deref()).await?;

            let (mut send, mut recv) = conn
                .open_bi()
                .await
                .map_err(|e| js_err(format!("open_bi failed: {e}")))?;

            send.write_all(&[STREAM_TYPE_CONTROL])
                .await
                .map_err(|e| js_err(format!("write: {e}")))?;
            send.write_all(b"PING\n")
                .await
                .map_err(|e| js_err(format!("write: {e}")))?;
            send.finish()
                .map_err(|e| js_err(format!("finish: {e}")))?;

            tracing::info!("ping: sent PING");

            let mut buf = Vec::new();
            let mut chunk = [0u8; 1024];
            while let Some(n) = recv
                .read(&mut chunk)
                .await
                .map_err(|e| js_err(format!("read: {e}")))?
            {
                buf.extend_from_slice(&chunk[..n]);
            }

            let response = String::from_utf8(buf)
                .map_err(|e| js_err(format!("invalid UTF-8: {e}")))?;
            tracing::info!(response = %response.trim(), "ping: received response");
            Ok(JsValue::from_str(&response))
        })
    }

    /// Send an HTTP request through the iroh tunnel and return the response.
    ///
    /// Returns a JSON string:
    ///   { "status": 200, "headers": {...}, "body_b64": "...", "is_binary": true }
    ///   { "status": 200, "headers": {...}, "body": "...", "is_binary": false }
    ///
    /// Binary bodies (video segments, etc.) are base64-encoded to avoid corruption
    /// from UTF-8 string conversion. Text bodies (JSON, HLS manifests) are returned as
    /// plain strings for efficiency.
    pub fn http_fetch(
        &self,
        method: String,
        path: String,
        headers_json: String,
        body: Option<String>,
    ) -> js_sys::Promise {
        let persistent = self.persistent_conn.clone();
        let endpoint = self.endpoint.clone();
        let server_id = self.server_endpoint_id.clone();

        future_to_promise(async move {
            tracing::info!("http_fetch: {method} {path}");

            let conn = get_or_reconnect(&persistent, &endpoint, server_id.as_deref()).await?;

            let (mut send, mut recv) = conn
                .open_bi()
                .await
                .map_err(|e| {
                    tracing::error!("http_fetch: open_bi failed: {e}");
                    js_err(format!("open_bi failed: {e}"))
                })?;

            // Write HTTP stream-type prefix
            send.write_all(&[STREAM_TYPE_HTTP])
                .await
                .map_err(|e| js_err(format!("write prefix: {e}")))?;

            // Build a raw HTTP/1.1 request
            let body_bytes = body.as_deref().unwrap_or("");
            let mut request = format!("{method} {path} HTTP/1.1\r\nHost: localhost\r\n");

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

            tracing::info!("http_fetch: sending {} byte request", request.len());
            send.write_all(request.as_bytes())
                .await
                .map_err(|e| js_err(format!("write request: {e}")))?;
            send.finish()
                .map_err(|e| js_err(format!("finish: {e}")))?;

            // Read the full HTTP response
            let mut response_buf = Vec::new();
            let mut chunk = [0u8; 8192];
            let mut read_count = 0u32;
            loop {
                match recv.read(&mut chunk).await {
                    Ok(Some(n)) => {
                        read_count += 1;
                        response_buf.extend_from_slice(&chunk[..n]);
                    }
                    Ok(None) => {
                        tracing::info!(
                            "http_fetch: stream finished, {read_count} reads, {} bytes",
                            response_buf.len()
                        );
                        break;
                    }
                    Err(e) => {
                        tracing::error!(
                            "http_fetch: read error after {read_count} reads ({} bytes): {e}",
                            response_buf.len()
                        );
                        if response_buf.is_empty() {
                            return Err(js_err(format!("read error: {e}")).into());
                        }
                        break;
                    }
                }
            }

            let result = parse_http_response_bytes(&response_buf);
            Ok(JsValue::from_str(&result))
        })
    }
}

// ---------------------------------------------------------------------------
// Persistent connection helper
// ---------------------------------------------------------------------------

async fn get_or_reconnect(
    persistent: &SharedConn,
    endpoint: &iroh::Endpoint,
    server_id: Option<&str>,
) -> Result<iroh::endpoint::Connection, JsValue> {
    // Take a clone of the current connection (if any) without holding the borrow
    let existing = persistent.borrow().clone();

    if let Some(ref conn) = existing {
        if conn.close_reason().is_none() {
            return Ok(conn.clone());
        }
        tracing::warn!("persistent connection closed, reconnecting");
    }

    let sid = server_id.ok_or_else(|| js_err("not connected — call connect() first"))?;
    let helper = KondooitConnection::new(endpoint.clone());
    let conn = helper.connect(sid).await.map_err(|e| {
        tracing::error!("reconnect failed: {e}");
        js_err(e)
    })?;
    tracing::info!("reconnected to server");
    *persistent.borrow_mut() = Some(conn.clone());
    Ok(conn)
}

// ---------------------------------------------------------------------------
// HTTP response parsing (binary-safe)
// ---------------------------------------------------------------------------

fn parse_http_response_bytes(raw: &[u8]) -> String {
    let sep = b"\r\n\r\n";
    let header_end = match find_subslice(raw, sep) {
        Some(pos) => pos,
        None => return serde_json::json!({ "status": 0, "headers": {}, "body": "", "is_binary": false }).to_string(),
    };

    let header_bytes = &raw[..header_end];
    let body_bytes = &raw[header_end + sep.len()..];

    let header_str = String::from_utf8_lossy(header_bytes);
    let mut lines = header_str.lines();

    let status: u16 = lines
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);

    let mut headers = serde_json::Map::new();
    let mut is_chunked = false;
    for line in lines {
        if let Some((key, value)) = line.split_once(':') {
            let key_lower = key.trim().to_lowercase();
            let val_trimmed = value.trim().to_string();
            if key_lower == "transfer-encoding" && val_trimmed.to_lowercase().contains("chunked") {
                is_chunked = true;
            }
            headers.insert(key_lower, serde_json::Value::String(val_trimmed));
        }
    }

    let body_bytes = if is_chunked {
        decode_chunked_bytes(body_bytes)
    } else {
        body_bytes.to_vec()
    };

    let is_binary = !body_bytes.is_empty() && String::from_utf8(body_bytes.as_slice()).is_err();

    let result = if is_binary {
        let b64 = base64::engine::general_purpose::STANDARD.encode(&body_bytes);
        serde_json::json!({
            "status": status,
            "headers": headers,
            "body_b64": b64,
            "is_binary": true,
        })
    } else {
        let body_str = String::from_utf8_lossy(&body_bytes).into_owned();
        serde_json::json!({
            "status": status,
            "headers": headers,
            "body": body_str,
            "is_binary": false,
        })
    };

    result.to_string()
}

fn decode_chunked_bytes(raw: &[u8]) -> Vec<u8> {
    let mut result = Vec::new();
    let mut pos = 0;

    while pos < raw.len() {
        let line_end = match find_subslice(&raw[pos..], b"\r\n") {
            Some(rel) => pos + rel,
            None => break,
        };

        let size_str = match std::str::from_utf8(&raw[pos..line_end]) {
            Ok(s) => s.trim(),
            Err(_) => break,
        };
        let chunk_size = match usize::from_str_radix(size_str, 16) {
            Ok(s) => s,
            Err(_) => break,
        };

        if chunk_size == 0 {
            break;
        }

        let data_start = line_end + 2;
        let data_end = data_start + chunk_size;
        if data_end > raw.len() {
            result.extend_from_slice(&raw[data_start..]);
            break;
        }

        result.extend_from_slice(&raw[data_start..data_end]);

        pos = data_end + 2;
        if pos >= raw.len() {
            break;
        }
    }

    result
}

fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || needle.len() > haystack.len() {
        return None;
    }
    (0..=haystack.len() - needle.len()).find(|&i| &haystack[i..i + needle.len()] == needle)
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
