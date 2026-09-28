//! Kondooit browser runtime — shared connection logic.
//!
//! This module defines the core iroh connection types and protocol constants
//! used by the browser WASM runtime. The `wasm` module wraps these for
//! JavaScript interop via wasm-bindgen.

pub mod wasm;

// ---------------------------------------------------------------------------
// Protocol constants
// ---------------------------------------------------------------------------

/// The ALPN protocol identifier for Kondooit tunnel connections.
/// This MUST match the ALPN used by the server-side sidecar.
pub const ALPN: &[u8] = b"kondooit/tunnel/0";

/// Stream-type prefixes (first byte of every bidi stream).
pub const STREAM_TYPE_HTTP: u8 = 0x00;
pub const STREAM_TYPE_CONTROL: u8 = 0x01;

// ---------------------------------------------------------------------------
// KondooitConnection
// ---------------------------------------------------------------------------

/// Holds an iroh `Endpoint` and manages connections to remote Kondooit servers.
pub struct KondooitConnection {
    endpoint: iroh::Endpoint,
}

impl KondooitConnection {
    /// Create a new connection wrapper around an existing endpoint.
    pub fn new(endpoint: iroh::Endpoint) -> Self {
        Self { endpoint }
    }

    /// Return a reference to the underlying iroh endpoint.
    pub fn endpoint(&self) -> &iroh::Endpoint {
        &self.endpoint
    }

    /// Connect to a remote Kondooit server by its endpoint ID (public key).
    pub async fn connect(
        &self,
        endpoint_id: &str,
    ) -> Result<iroh::endpoint::Connection, ConnectError> {
        let peer_id: iroh::EndpointId = endpoint_id
            .trim()
            .parse()
            .map_err(|e| ConnectError::InvalidEndpointId(format!("{e}")))?;

        let addr = iroh::EndpointAddr::from(peer_id);

        tracing::info!(%peer_id, "connecting to server...");

        let conn = self
            .endpoint
            .connect(addr, ALPN)
            .await
            .map_err(|e| ConnectError::Connection(format!("{e}")))?;

        tracing::info!(%peer_id, "connected");
        Ok(conn)
    }

    /// MVP test: open a control bidi stream, write "PING\n", read the response.
    pub async fn ping(
        &self,
        endpoint_id: &str,
    ) -> Result<String, ConnectError> {
        let conn = self.connect(endpoint_id).await?;

        let (mut send, mut recv) = conn
            .open_bi()
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        // Write the control stream-type prefix, then the PING payload
        send.write_all(&[STREAM_TYPE_CONTROL])
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;
        send.write_all(b"PING\n")
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;
        send.finish()
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        tracing::info!("sent PING (control stream)");

        let mut buf = Vec::new();
        let mut chunk = [0u8; 1024];
        while let Some(n) = recv
            .read(&mut chunk)
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?
        {
            buf.extend_from_slice(&chunk[..n]);
        }

        conn.close(0u32.into(), b"done");

        let response = String::from_utf8(buf)
            .map_err(|e| ConnectError::Protocol(format!("invalid UTF-8 response: {e}")))?;

        tracing::info!(response = %response.trim(), "received response");
        Ok(response)
    }

    /// Open an HTTP-tunneled bidi stream to the server.
    /// Returns (send, recv) with the HTTP prefix already written.
    pub async fn open_http_stream(
        &self,
        conn: &iroh::endpoint::Connection,
    ) -> Result<(iroh::endpoint::SendStream, iroh::endpoint::RecvStream), ConnectError> {
        let (mut send, recv) = conn
            .open_bi()
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        send.write_all(&[STREAM_TYPE_HTTP])
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        Ok((send, recv))
    }
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/// Errors that can occur when connecting to a Kondooit server.
#[derive(Debug)]
pub enum ConnectError {
    InvalidEndpointId(String),
    Connection(String),
    Stream(String),
    Protocol(String),
}

impl std::fmt::Display for ConnectError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidEndpointId(e) => write!(f, "invalid endpoint ID: {e}"),
            Self::Connection(e) => write!(f, "connection failed: {e}"),
            Self::Stream(e) => write!(f, "stream error: {e}"),
            Self::Protocol(e) => write!(f, "protocol error: {e}"),
        }
    }
}

impl std::error::Error for ConnectError {}
