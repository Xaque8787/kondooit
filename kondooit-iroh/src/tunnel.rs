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
///
/// Sequential: forward the full request, then read the full response.
/// The response is read by parsing HTTP headers to determine the body
/// length (Content-Length or chunked), rather than waiting for TCP EOF,
/// because HTTP keep-alive connections don't close after a single response.
async fn proxy_to_tcp(
    mut send: iroh::endpoint::SendStream,
    mut recv: iroh::endpoint::RecvStream,
    addr: &str,
) -> Result<()> {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};

    info!("HTTP proxy: connecting to {addr}");
    let mut tcp = TcpStream::connect(addr).await?;
    let (mut tcp_read, mut tcp_write) = tcp.split();

    // 1. Forward complete request: iroh → TCP
    let req_bytes = tokio::io::copy(&mut recv, &mut tcp_write).await?;
    tcp_write.shutdown().await?;
    info!("HTTP proxy: forwarded {req_bytes} request bytes, reading response headers");

    // 2. Read the HTTP response headers, then the exact body length.
    let mut header_buf = Vec::with_capacity(4096);
    let mut byte = [0u8; 1];

    loop {
        let n = tcp_read.read(&mut byte).await?;
        if n == 0 {
            info!("HTTP proxy: connection closed before headers complete ({} bytes read)", header_buf.len());
            send.write_all(&header_buf).await?;
            let _ = send.finish();
            return Ok(());
        }
        header_buf.push(byte[0]);
        if header_buf.len() >= 4 && header_buf[header_buf.len() - 4..] == *b"\r\n\r\n" {
            break;
        }
        if header_buf.len() > 65536 {
            anyhow::bail!("HTTP response headers too large");
        }
    }

    let header_str = String::from_utf8_lossy(&header_buf);
    let content_length = parse_content_length(&header_str);
    let is_chunked = header_str
        .lines()
        .any(|l| {
            let lower = l.to_lowercase();
            lower.starts_with("transfer-encoding:") && lower.contains("chunked")
        });

    info!(
        "HTTP proxy: headers={} bytes, content_length={:?}, chunked={}",
        header_buf.len(), content_length, is_chunked
    );

    send.write_all(&header_buf).await?;

    if is_chunked {
        let mut chunk_buf = Vec::new();
        loop {
            let mut size_line = Vec::new();
            loop {
                let n = tcp_read.read(&mut byte).await?;
                if n == 0 { break; }
                size_line.push(byte[0]);
                if size_line.len() >= 2 && size_line[size_line.len() - 2..] == *b"\r\n" {
                    break;
                }
            }
            let size_str = String::from_utf8_lossy(&size_line);
            let chunk_size = usize::from_str_radix(size_str.trim(), 16).unwrap_or(0);
            chunk_buf.extend_from_slice(&size_line);

            if chunk_size == 0 {
                let mut trailer = [0u8; 2];
                let _ = tcp_read.read_exact(&mut trailer).await;
                chunk_buf.extend_from_slice(&trailer);
                break;
            }

            let mut data = vec![0u8; chunk_size + 2];
            tcp_read.read_exact(&mut data).await?;
            chunk_buf.extend_from_slice(&data);
        }
        info!("HTTP proxy: chunked body={} bytes", chunk_buf.len());
        send.write_all(&chunk_buf).await?;
    } else if let Some(len) = content_length {
        if len > 0 {
            let mut body = vec![0u8; len];
            tcp_read.read_exact(&mut body).await?;
            send.write_all(&body).await?;
        }
        info!("HTTP proxy: content-length body={} bytes", len);
    } else {
        let n = tokio::io::copy(&mut tcp_read, &mut send).await?;
        info!("HTTP proxy: read-until-eof body={n} bytes");
    }

    let _ = send.finish();
    info!("HTTP proxy: response complete");
    Ok(())
}

fn parse_content_length(headers: &str) -> Option<usize> {
    for line in headers.lines() {
        let lower = line.to_lowercase();
        if lower.starts_with("content-length:") {
            if let Some(val) = line.split_once(':') {
                return val.1.trim().parse().ok();
            }
        }
    }
    None
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
