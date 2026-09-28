use std::fmt;
use std::sync::Arc;

use anyhow::Result;
use iroh::endpoint::Connection;
use iroh::protocol::AcceptError;
use tokio::net::TcpStream;
use tracing::{info, warn};

/// ALPN protocol identifier for kondooit tunnels.
pub const ALPN: &[u8] = b"kondooit/tunnel/0";

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

        // Accept bidi streams in a loop until the connection closes.
        loop {
            let (send, recv) = match connection.accept_bi().await {
                Ok(pair) => pair,
                Err(_) => break, // connection closed
            };

            let addr = format!("127.0.0.1:{port}");
            tokio::spawn(async move {
                if let Err(e) = handle_stream(send, recv, &addr).await {
                    warn!("stream tunnel error: {e:#}");
                }
            });
        }

        Ok(())
    }
}

/// Pipe a single bidi stream to a TCP connection and back.
async fn handle_stream(
    mut send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
    addr: &str,
) -> Result<()> {
    let mut tcp = TcpStream::connect(addr).await?;
    let (mut tcp_read, mut tcp_write) = tcp.split();

    // iroh SendStream implements AsyncWrite, RecvStream implements AsyncRead.
    // Pipe both directions concurrently.
    let client_to_server = tokio::io::copy(&mut recv, &mut tcp_write);
    let server_to_client = tokio::io::copy(&mut tcp_read, &mut send);

    // Run both directions; when either finishes, we're done.
    tokio::select! {
        r = client_to_server => {
            r?;
        }
        r = server_to_client => {
            r?;
        }
    }

    // Best-effort finish the send stream.
    let _ = send.finish();
    Ok(())
}
