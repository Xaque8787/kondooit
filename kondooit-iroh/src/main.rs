mod control;
mod endpoint;
mod tunnel;

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use clap::Parser;
use iroh::protocol::Router;
use tokio::sync::Notify;
use tracing::info;

#[derive(Parser, Debug)]
#[command(name = "kondooit-iroh", about = "Iroh tunnel sidecar for kondooit")]
struct Args {
    /// Directory for persisting iroh identity and state.
    #[arg(long, default_value = "/data/iroh")]
    data_dir: PathBuf,

    /// Local TCP port to tunnel HTTP traffic to.
    #[arg(long, default_value_t = 8000)]
    target_port: u16,

    /// Path for the Unix socket control API.
    #[arg(long, default_value = "/tmp/kondooit-iroh.sock")]
    control_socket: PathBuf,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "kondooit_iroh=info,iroh=warn".into()),
        )
        .init();

    let args = Args::parse();
    info!(?args, "starting kondooit-iroh sidecar");

    // 1. Create the iroh endpoint with persistent identity.
    let ep = endpoint::create_endpoint(&args.data_dir).await?;

    // 2. Wait for relay connectivity.
    ep.online().await;
    info!(id = %ep.id(), "endpoint online");

    // 3. Build the protocol router with our tunnel handler.
    let handler = tunnel::TunnelHandler::new(args.target_port);
    let router = Router::builder(ep.clone())
        .accept(tunnel::ALPN, handler)
        .spawn();

    info!("tunnel router spawned, accepting connections");

    // 4. Run the control socket in the background.
    let shutdown_notify = Arc::new(Notify::new());
    let control_handle = {
        let ep = ep.clone();
        let path = args.control_socket.clone();
        let notify = shutdown_notify.clone();
        tokio::spawn(async move {
            if let Err(e) = control::run_control_socket(&path, ep, notify).await {
                tracing::error!("control socket error: {e:#}");
            }
        })
    };

    // 5. Wait for shutdown signal (ctrl-c or control socket command).
    let notify = shutdown_notify.clone();
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("received ctrl-c, shutting down");
        }
        _ = notify.notified() => {
            info!("shutdown requested via control socket");
        }
    }

    // 6. Graceful shutdown.
    router.shutdown().await?;
    control_handle.abort();
    info!("goodbye");

    Ok(())
}
