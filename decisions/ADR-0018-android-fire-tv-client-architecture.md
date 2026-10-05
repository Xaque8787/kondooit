# ADR-0018: Android / Fire TV client architecture — Kotlin UI with shared Rust core via uniFFI

- **Status:** Proposed
- **Date:** 2026-10-05
- **Supersedes:** —
- **Superseded by:** —
- **Resolves:** "How should native Android/Fire TV clients be built, and how do they share the iroh connection logic with the browser runtime?" (new open question, recorded in `architecture/OPEN_QUESTIONS.md`)

## Context

The Kondooit vision describes thin clients that authenticate, browse the server's unified catalog, request playback, and receive media. The server holds all media intelligence. The web client (`web/`) and the browser iroh runtime (`kondooit-runtime/`) already exist. Native Android and Fire TV clients are the next logical client targets — Fire TV is the primary TV platform for many household users.

The existing Rust code in `kondooit-runtime/src/lib.rs` implements iroh connection management, the HTTP tunnel protocol, stream type dispatch, and binary-safe response parsing. This logic is currently compiled to WASM for browser use. An Android client needs the same logic. Rewriting it in another language would duplicate the tunnel protocol, risk protocol drift between platforms, and discard the debugging work already invested (including the binary-safety fix for video segment responses).

This ADR documents the recommended approach so it can be implemented when the roadmap authorizes native client development. It is not authorized for implementation in the current milestone.

### Key constraints

1. **Fire TV is an Android variant.** Fire TV devices run Amazon's fork of Android (Fire OS) and support standard Android APKs. A single Android app targeting Fire TV and standard Android phones/tablets is feasible. AndroidX Leanback and TV Compose libraries provide TV-optimized UI components.

2. **The iroh connection logic already exists in Rust.** `kondooit-runtime/src/lib.rs` contains connection management, HTTP tunnel protocol, stream type dispatch, and binary-safe parsing. This is the same logic both the browser WASM runtime and an Android native client would need. Duplicating it in Kotlin would mean maintaining the tunnel protocol in two languages.

3. **Android has native video playback infrastructure.** Media3/ExoPlayer is the standard Android media player. It supports HLS, DASH, progressive download, adaptive streaming, and codec selection. This is significantly more capable than browser-based HLS.js for video playback on TV devices.

4. **Native iroh connections bypass the relay.** Unlike browsers (which cannot open raw UDP/QUIC sockets), native Android clients can establish direct iroh connections via NAT hole-punching. This means media delivery for remote native clients can potentially bypass the relay entirely, reducing latency and relay bandwidth.

5. **The server treats all clients identically.** The server's HTTP API does not distinguish between web, Android, or other clients. The Android client speaks the same HTTP API (whether over LAN HTTP or tunneled over iroh) as the web client.

## Decision

### 1. Architecture overview

```
kondooit-core (new Rust crate — pure logic, no platform dependencies)
    ├── iroh connection management
    ├── HTTP tunnel protocol
    ├── stream type dispatch
    └── binary-safe response parsing

kondooit-runtime (browser)     → wraps core as WASM (existing)
kondooit-android (future)      → wraps core via uniFFI, Kotlin UI
```

Extract the shared iroh/tunnel logic from `kondooit-runtime/src/lib.rs` into a new `kondooit-core` crate with no platform-specific dependencies. The browser runtime depends on `kondooit-core` and adds the WASM bindings layer. The Android app depends on `kondooit-core` and adds uniFFI-generated Kotlin bindings plus the native UI.

### 2. Kotlin for the UI layer

**Why Kotlin:**
- First-class Android and Fire TV support
- Media3/ExoPlayer for video playback (HLS, DASH, progressive, adaptive bitrate)
- AndroidX Leanback / TV Compose for TV-optimized interfaces with D-pad navigation
- Native lifecycle management, background services, notification controls
- Access to platform DRM APIs if needed in the future
- Coroutines for async networking alongside the Rust core's async operations

**What the Kotlin layer does:**
- Browse the Kondooit catalog (movies, series, episodes) via the HTTP API
- Authenticate to the Kondooit server
- Request playback and receive stream handles
- Play media via Media3/ExoPlayer, handling both direct URLs and proxy-mode stream handles
- TV-optimized UI with D-pad/remote navigation, poster grids, detail pages
- Profile selection, watch progress sync, user settings

**What the Kotlin layer does NOT do:**
- Any media intelligence (metadata resolution, source discovery, ranking) — that lives on the server
- Direct communication with providers (TMDB, TVDB, Debrid, etc.) — the server mediates all provider interactions
- Local media scanning or file management — the server is the source of truth

### 3. Rust shared core via uniFFI

**What uniFFI does:**
- Generates Kotlin (and Swift, and other language) bindings from Rust crate interface definitions
- The Kotlin UI calls into the Rust core through generated Kotlin interfaces — no manual JNI boilerplate
- The Rust core handles iroh connection management, the HTTP tunnel protocol, stream type dispatch, and binary-safe response parsing

**What stays in the Rust core:**
- iroh endpoint initialization and connection management
- HTTP request tunneling over iroh bidirectional streams
- Response parsing with binary-safety detection (the `std::str::from_utf8` check and base64 fallback)
- Stream type dispatch (text vs binary, JSON vs media segments)

**What stays out of the Rust core:**
- Any UI logic
- Any Android platform APIs
- Any video playback logic (that's Media3/ExoPlayer in Kotlin)
- Any Android lifecycle management

### 4. Repository structure

The Android app lives in the monorepo alongside the other components:

```
kondooit-android/           (new directory — future)
  app/
    build.gradle.kts
    src/main/kotlin/
      ...Kotlin UI and ExoPlayer integration...
  jniLibs/                   (populated by CI, not committed)
    arm64-v8a/libkondooit_core.so
    armeabi-v7a/libkondooit_core.so
    x86_64/libkondooit_core.so
  build.gradle.kts           (root)
  settings.gradle.kts
```

The `kondooit-core` crate lives alongside the existing Rust crates:

```
kondooit-core/              (new Rust crate — extracted from kondooit-runtime)
  src/
    lib.rs
  Cargo.toml
  uniffi.toml
```

`kondooit-runtime/` is refactored to depend on `kondooit-core` for the shared logic and keep only the WASM-specific bindings layer.

### 5. CI / CD (GitHub Actions)

The APK build is a GitHub Actions workflow with these stages:

1. **Install Rust toolchain** with Android targets (`aarch64-linux-android`, `armv7-linux-androideabi`, `x86_64-linux-android`)
2. **Install Android NDK** (or use the pre-installed one on the GitHub-hosted runner)
3. **Build Rust core as `.so` libraries** for each target ABI using `cargo-ndk`
4. **Generate uniFFI Kotlin bindings** via `cargo run --bin uniffi-bindgen kotlin`
5. **Run Gradle `assembleRelease`** (or `assembleDebug`) to compile Kotlin and package the APK
6. **Sign the APK** using a keystore stored in GitHub Actions secrets
7. **Upload the APK** as a build artifact

**Existing reference:** `.github/workflows/deploy-runtime.yml` already builds the WASM runtime with `wasm-pack`. The Android Rust cross-compilation is the same concept with different target triples and linker configuration.

**Build time optimization:** For faster iteration, build only `aarch64-linux-android` (covers all modern Fire TV devices and most Android phones). Add `armv7` and `x86_64` for release builds.

**Caching:** Use `swatinem/rust-cache` for Rust compilation artifacts and `gradle/actions/setup-gradle` for Gradle dependency caching.

### 6. Delivery mode for native clients

Native Android clients can establish direct iroh connections (NAT hole-punching) without requiring a relay for media delivery. This is an advantage over browser clients. The delivery matrix from ADR-0017 extends:

- **Direct-playable source, native client, LAN:** Direct delivery (client fetches from CDN)
- **Direct-playable source, native client, remote:** Direct delivery (client fetches from CDN directly — relay sees only control traffic)
- **Remux/transcode needed, native client, LAN:** Server proxy (localhost is fast)
- **Remux/transcode needed, native client, remote:** Server proxy through direct iroh connection (bypasses relay if hole-punching succeeds; falls back to relay if not)
- **Local file source, native client, any:** Server proxy through iroh (file is only on server)

The `force_proxy_remote` profile preference from ADR-0017 applies identically to native clients.

### 7. What is NOT decided by this ADR

- **iOS / Apple TV client.** The same `kondooit-core` crate could serve an iOS app via uniFFI-generated Swift bindings. The architecture supports this. However, iOS/Apple TV implementation has additional constraints (Xcode build requirement, Apple's signing/notarization process, no sideloading on Apple TV) that warrant a separate decision when that work is authorized.

- **The specific TV UI design.** This ADR decides the technology (Kotlin + Compose for TV / Leanback), not the UI/UX design. The UI design is an implementation concern for when the work is authorized.

- **Android Auto / Android Wear.** Not considered. The scope is phone + Fire TV / Android TV.

- **Play Store vs. sideloading distribution.** Fire TV apps are typically sideloaded (Amazon's Appstore has restrictions). Android phone apps could go on the Play Store. Distribution strategy is a separate decision.

- **DRM support.** Media3 supports Widevine and other DRM schemes. Whether Kondooit needs DRM depends on future content source decisions. This is out of scope for the initial Android client.

## Rationale

- **Reuse the Rust iroh logic.** The connection management, HTTP tunnel protocol, and binary-safe parsing in `kondooit-runtime/src/lib.rs` are already written and debugged. Extracting them into a shared `kondooit-core` crate and consuming them from both WASM and Android avoids protocol drift and code duplication. This is the same "shared core crate" pattern identified in the mydia research (section 3.1).

- **Kotlin gives the best Android/Fire TV experience.** Media3/ExoPlayer is the most capable Android media player. AndroidX Leanback and TV Compose provide TV-optimized components with D-pad navigation. No cross-platform framework (React Native, Flutter) offers comparable TV support or native media playback.

- **uniFFI is the standard Rust-to-mobile bridge.** Used by Signal, Mozilla, and other production apps. Generates type-safe Kotlin bindings from Rust interfaces without manual JNI boilerplate. The same crate can later generate Swift bindings for iOS.

- **Monorepo keeps the shared core in sync.** A change to the tunnel protocol or iroh connection logic is one commit — update `kondooit-core`, regenerate WASM and uniFFI bindings in the same PR, CI builds both. A separate repo would require crate publishing or submodule bumps and cross-repo coordination.

- **GitHub Actions can build the full pipeline.** Rust cross-compilation to Android ABIs + uniFFI binding generation + Gradle APK assembly is a well-established CI pattern. No external CI service needed.

## Alternatives considered

- **React Native.** Rejected because: no mature TV-optimized component library (AndroidX Leanback / TV Compose have no React Native equivalent); iroh would require a custom native module (re-introducing JNI/Rust bridging anyway); and the rendering model (bridge-based) adds latency on low-powered TV hardware. No benefit over Kotlin when the Rust core already handles the networking layer.

- **Flutter.** Rejected because: the mydia project uses Flutter and it works, but it would introduce a second rendering framework alongside the existing React web client for no architectural benefit; iroh would still need FFI to Rust (same uniFFI pattern, different bindings); and Flutter's TV support is less mature than Android's native Leanback/TV Compose libraries.

- **Pure Rust UI (e.g., Slint, Tauri Mobile).** Rejected because: no mature Android TV UI toolkit exists in the Rust ecosystem; fighting the platform for TV-specific features (D-pad navigation, system media controls, DRM) would consume more effort than the app itself; and the Rust core is deliberately pure logic — keeping UI out of it preserves the boundary.

- **Kotlin with a Kotlin-native iroh client (no Rust shared core).** Rejected because: the iroh connection logic, HTTP tunnel protocol, and binary-safe parsing already exist in Rust and are debugged. Rewriting in Kotlin would duplicate the protocol, risk drift between the browser and Android clients, and discard the binary-safety fix. The maintenance cost of two implementations is higher than the one-time uniFFI setup cost.

- **Separate repository for the Android app.** Rejected because: the Android app shares a Rust core crate with the browser runtime. In a separate repo, changes to the shared crate would require crate publishing or submodule bumps and cross-repo coordination. The existing repo is already a monorepo with clear directory boundaries (`server/`, `web/`, `kondooit-runtime/`, `kondooit-iroh/`, `scraper_modules/`). Adding `kondooit-android/` follows the same pattern.

## Consequences

- A new `kondooit-core` Rust crate is created by extracting shared logic from `kondooit-runtime/src/lib.rs`. The browser runtime is refactored to depend on this crate.
- A new `kondooit-android/` directory is added to the repository with a Gradle project structure.
- CI gains a workflow for Rust Android cross-compilation + uniFFI binding generation + Gradle APK assembly.
- The `kondooit-core` crate gains a `uniffi.toml` and `cargo-ndk` build configuration for Android targets.
- The `kondooit-core` crate's interface must be designed with uniFFI-compatible types (plain structs, enums, callbacks for async operations).
- No changes to the server, the domain layer, or the application layer. The Android client is a thin client that speaks the same HTTP API as the web client.
- The `kondooit-runtime` WASM build remains unchanged in behavior — it depends on `kondooit-core` but produces the same WASM output.

## Relationship to other ADRs

- **ADR-0007** (iroh default transport): The Android client uses iroh for remote access, consistent with iroh as the default transport. The shared Rust core implements the same HTTP-over-iroh tunneling.
- **ADR-0008** (Technology baseline): Kotlin is a new client implementation technology, not a domain or server technology. It does not affect the server technology stack. Rust is already an accepted technology for iroh infrastructure. uniFFI is a build tool, not an architectural concept.
- **ADR-0014** (Direct delivery default): The Android client receives direct delivery stream handles for CDN-backed sources, same as the web client.
- **ADR-0015** (Stream handle delivery modes): The Android client handles both `direct` and `proxy` stream handles. Proxy-mode playback uses Media3/ExoPlayer with the proxy URL from the stream handle.
- **ADR-0017** (iroh remote access architecture): The Android client connects via iroh using the same ticket model. Native iroh connections can bypass the relay for media delivery when hole-punching succeeds — an advantage over browser clients that the delivery matrix accounts for.
