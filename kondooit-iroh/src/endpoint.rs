use std::path::Path;

use anyhow::{Context, Result};
use iroh::{Endpoint, SecretKey, endpoint::presets};
use tracing::info;

/// Load or generate a persistent identity key.
fn load_or_create_secret_key(path: &Path) -> Result<SecretKey> {
    if path.exists() {
        let bytes = std::fs::read(path).context("reading secret key")?;
        let bytes: [u8; 32] = bytes
            .try_into()
            .map_err(|_| anyhow::anyhow!("invalid secret key length"))?;
        Ok(SecretKey::from_bytes(&bytes))
    } else {
        let key = SecretKey::generate();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).context("creating key directory")?;
        }
        std::fs::write(path, key.to_bytes()).context("writing secret key")?;
        info!("generated new identity at {}", path.display());
        Ok(key)
    }
}

/// Create an iroh endpoint with the N0 relay preset and a persistent identity.
pub async fn create_endpoint(data_dir: &Path) -> Result<Endpoint> {
    let key_path = data_dir.join("secret-key");
    let secret_key = load_or_create_secret_key(&key_path)?;

    let endpoint = Endpoint::builder(presets::N0)
        .secret_key(secret_key)
        .bind()
        .await
        .context("binding iroh endpoint")?;

    info!(id = %endpoint.id(), "iroh endpoint bound");
    Ok(endpoint)
}
