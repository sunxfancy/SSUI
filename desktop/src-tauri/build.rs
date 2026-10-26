fn main() {
    if std::env::var_os("CARGO_FEATURE_NATIVE_TESTS").is_some() {
        // Tauri codegen reads the standard filename and merges TAURI_CONFIG.
        // Keep build-time ACL generation and macro asset embedding on the same config.
        let config = include_str!("tauri.test.conf.json").lines().collect::<String>();
        std::env::set_var("TAURI_CONFIG", &config);
        println!("cargo:rustc-env=TAURI_CONFIG={config}");
        println!("cargo:rerun-if-changed=tauri.test.conf.json");
    }
    tauri_build::build()
}
