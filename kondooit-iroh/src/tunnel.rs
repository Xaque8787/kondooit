use std::fmt;
use std::sync::Arc;

use anyhow::Result;
use iroh::endpoint::Connection;
use iroh::protocol::AcceptError;
use tokio::net::TcpStream;
use tracing::{info, warn};

/// ALPN protocol identifier for kondooit tunnels.
pub const ALPN: &[u8] = b"kondooit/tunnel/0";

/// Stream-type prefixes. The first byte of every bidi stream determines how
/// the sidecar handles it.
pub const STREAM_TYPE_HTTP: u8 = 0x00;
pub const STREAM_TYPE_CONTROL: u8 = 0x01;

/// Protocol handler that tunnels each incoming bidi stream to a local TCP port.
#[derive(Clone)]
pub struct TunnelHandler {
    target_port: u16,
}

impl fmt::Debug for TunnelHandler {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("TunnelHandler")
            .field("target_port", &self.target_port)
            .finish()
    }
}

impl TunnelHandler {
    pub fn new(target_port: u16) -> Arc<Self> {
        Arc::new(Self { target_port })
    }
}

impl iroh::protocol::ProtocolHandler for TunnelHandler {
    async fn accept(&self, connection: Connection) -> Result<(), AcceptError> {
        let port = self.target_port;
        info!("new tunnel connection");

        loop {
            let (send, recv) = match connection.accept_bi().await {
                Ok(pair) => pair,
                Err(_) => break,
            };

            let addr = format!("127.0.0.1:{port}");
            tokio::spawn(async move {
                if let Err(e) = dispatch_stream(send, recv, &addr).await {
                    warn!("stream dispatch error: {e:#}");
                }
            });
        }

        Ok(())
    }
}

/// Read the 1-byte stream-type prefix and dispatch accordingly.
async fn dispatch_stream(
    send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
    addr: &str,
) -> Result<()> {
    let mut prefix = [0u8; 1];
    recv.read_exact(&mut prefix)
        .await
        .map_err(|e| anyhow::anyhow!("failed to read stream-type prefix: {e}"))?;
    let stream_type = prefix[0];

    match stream_type {
        STREAM_TYPE_HTTP => proxy_to_tcp(send, recv, addr).await,
        STREAM_TYPE_CONTROL => handle_control(send, recv).await,
        other => {
            warn!(stream_type = other, "unknown stream-type prefix, dropping");
            Ok(())
        }
    }
}

/// Pipe a bidi stream to a TCP connection and back (HTTP proxy).
async fn proxy_to_tcp(
    mut send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
    addr: &str,
) -> Result<()> {
    let mut tcp = TcpStream::connect(addr).await?;
    let (mut tcp_read, mut tcp_write) = tcp.split();

    let client_to_server = tokio::io::copy(&mut recv, &mut tcp_write);
    let server_to_client = tokio::io::copy(&mut tcp_read, &mut send);

    tokio::select! {
        r = client_to_server => { r?; }
        r = server_to_client => { r?; }
    }

    let _ = send.finish();
    Ok(())
}

/// Handle a control stream (ping/pong, future extensions).
async fn handle_control(
    mut send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
) -> Result<()> {
    let mut buf = Vec::new();
    let mut chunk = [0u8; 1024];
    while let Some(n) = recv.read(&mut chunk).await? {
        buf.extend_from_slice(&chunk[..n]);
        if buf.len() > 4096 {
            break;
        }
    }

    let msg = String::from_utf8_lossy(&buf);
    let trimmed = msg.trim();
    info!(msg = trimmed, "control message received");

    let response = match trimmed {
        "PING" => "PONG\n",
        _ => "ERR: unknown command\n",
    };

    send.write_all(response.as_bytes()).await?;
    let _ = send.finish();
    Ok(())
}
