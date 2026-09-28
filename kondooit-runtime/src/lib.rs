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
    ///
    /// The `endpoint_id` is the hex-encoded iroh `NodeId`. Since browsers are
    /// relay-only, the connection flows through an iroh relay server and is
    /// end-to-end encrypted.
    pub async fn connect(
        &self,
        endpoint_id: &str,
    ) -> Result<iroh::endpoint::Connection, ConnectError> {
        let node_id: iroh::NodeId = endpoint_id
            .trim()
            .parse()
            .map_err(|e| ConnectError::InvalidEndpointId(format!("{e}")))?;

        let addr = iroh::EndpointAddr::from(node_id);

        tracing::info!(%node_id, "connecting to server…");

        let conn = self
            .endpoint
            .connect(addr, ALPN)
            .await
            .map_err(|e| ConnectError::Connection(format!("{e}")))?;

        tracing::info!(%node_id, "connected");
        Ok(conn)
    }

    /// MVP test: open a bidi stream, write "PING\n", read the response.
    ///
    /// Returns whatever the server sends back (expected: "PONG\n").
    pub async fn ping(
        &self,
        endpoint_id: &str,
    ) -> Result<String, ConnectError> {
        let conn = self.connect(endpoint_id).await?;

        let (mut send, mut recv) = conn
            .open_bi()
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        // Send PING
        send.write_all(b"PING\n")
            .await
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;
        send.finish()
            .map_err(|e| ConnectError::Stream(format!("{e}")))?;

        tracing::info!("sent PING");

        // Read response until the server closes its send side
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
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/// Errors that can occur when connecting to a Kondooit server.
#[derive(Debug)]
pub enum ConnectError {
    /// The endpoint ID string could not be parsed.
    InvalidEndpointId(String),
    /// The iroh connection failed.
    Connection(String),
    /// A stream operation (open/read/write) failed.
    Stream(String),
    /// Protocol-level error (unexpected data, encoding, etc.).
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
