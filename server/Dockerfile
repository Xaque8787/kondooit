FROM rust:1-bookworm AS iroh-builder
WORKDIR /build
COPY kondooit-iroh/ .
RUN cargo build --release

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=iroh-builder /build/target/release/kondooit-iroh /usr/local/bin/kondooit-iroh

COPY server/ .

RUN pip install --no-cache-dir -e ".[dev]"

RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
