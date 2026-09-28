use std::path::Path;
use std::sync::Arc;

use anyhow::{Context, Result};
use iroh::{Endpoint, EndpointAddr, Watcher};
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::Notify;
use tracing::{info, warn};

#[derive(Debug, Deserialize)]
struct Request {
    cmd: String,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum Response {
    Status {
        online: bool,
        endpoint_id: String,
        relay_connected: bool,
    },
    Ticket {
        ticket: String,
    },
    Shutdown {
        ok: bool,
    },
    Error {
        error: String,
    },
}

/// Run the Unix socket control API.
///
/// Listens for JSON-line commands and responds with JSON-line replies.
/// Signals `shutdown_notify` when a shutdown command arrives.
pub async fn run_control_socket(
    socket_path: &Path,
    endpoint: Endpoint,
    shutdown_notify: Arc<Notify>,
) -> Result<()> {
    // Remove stale socket file if present.
    let _ = std::fs::remove_file(socket_path);

    let listener = UnixListener::bind(socket_path)
        .with_context(|| format!("binding control socket at {}", socket_path.display()))?;

    info!(path = %socket_path.display(), "control socket listening");

    loop {
        tokio::select! {
            accept = listener.accept() => {
                match accept {
                    Ok((stream, _)) => {
                        let ep = endpoint.clone();
                        let notify = shutdown_notify.clone();
                        tokio::spawn(async move {
                            if let Err(e) = handle_client(stream, ep, notify).await {
                                warn!("control client error: {e:#}");
                            }
                        });
                    }
                    Err(e) => {
                        warn!("control accept error: {e:#}");
                    }
                }
            }
            _ = shutdown_notify.notified() => {
                info!("control socket shutting down");
                break;
            }
        }
    }

    let _ = std::fs::remove_file(socket_path);
    Ok(())
}

async fn handle_client(
    stream: UnixStream,
    endpoint: Endpoint,
    shutdown_notify: Arc<Notify>,
) -> Result<()> {
    let (read_half, mut write_half) = stream.into_split();
    let reader = BufReader::new(read_half);
    let mut lines = reader.lines();

    while let Some(line) = lines.next_line().await? {
        let response = match serde_json::from_str::<Request>(&line) {
            Ok(req) => handle_command(&req.cmd, &endpoint, &shutdown_notify).await,
            Err(e) => Response::Error {
                error: format!("invalid request: {e}"),
            },
        };

        let mut out = serde_json::to_string(&response)?;
        out.push('\n');
        write_half.write_all(out.as_bytes()).await?;

        // If it was a shutdown command, break after responding.
        if matches!(response, Response::Shutdown { ok: true }) {
            break;
        }
    }

    Ok(())
}

async fn handle_command(
    cmd: &str,
    endpoint: &Endpoint,
    shutdown_notify: &Notify,
) -> Response {
    match cmd {
        "status" => {
            let endpoint_id = endpoint.id().to_string();
            let relay_connected = !endpoint.home_relay_status().get().is_empty();
            Response::Status {
                online: true,
                endpoint_id,
                relay_connected,
            }
        }
        "ticket" => {
            let addr = EndpointAddr::from(endpoint.id());
            Response::Ticket {
                ticket: addr.to_string(),
            }
        }
        "shutdown" => {
            shutdown_notify.notify_waiters();
            Response::Shutdown { ok: true }
        }
        other => Response::Error {
            error: format!("unknown command: {other}"),
        },
    }
}
