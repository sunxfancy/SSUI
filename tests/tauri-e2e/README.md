# Tauri native smoke test

This suite verifies that a built SSUI executable opens its real Tauri WebView,
loads the React root, and finishes initialization. Business workflows remain in
the faster Playwright suite.

Prerequisites on Linux/Windows:

1. Install the platform WebDriver prerequisites from the Tauri documentation.
2. Install the driver with `cargo install tauri-driver --locked`.
3. Build without bundling: `yarn workspace ssui-desktop tauri build --debug --no-bundle`.
4. Run `yarn test:tauri-smoke`.

Set `SSUI_TAURI_BINARY` or `SSUI_TAURI_DRIVER` to override their default paths.
Direct `tauri-driver` does not support macOS; release packaging there continues
to use `scripts/smoke_app.cjs`. Cross-platform native DOM automation can later
adopt the embedded WebdriverIO Tauri service, which requires test-only Rust
plugins in the application binary.
