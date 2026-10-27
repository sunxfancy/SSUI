fn main() {
    if std::env::var_os("CARGO_FEATURE_NATIVE_TESTS").is_some() {
        // Tauri codegen reads the standard filename and merges TAURI_CONFIG.
        // Keep build-time ACL generation and macro asset embedding on the same config.
        let config = include_str!("tauri.test.conf.json").lines().collect::<String>();
        std::env::set_var("TAURI_CONFIG", &config);
        println!("cargo:rustc-env=TAURI_CONFIG={config}");
        println!("cargo:rerun-if-changed=tauri.test.conf.json");
    }
    tauri_build::build();
    if std::env::var_os("CARGO_FEATURE_NATIVE_TESTS").is_some()
        && std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows")
        && std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc")
    {
        // tauri-winres links this resource only to bin targets. The native-test
        // example also needs its Common Controls v6 manifest to start on Windows.
        let resource = std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap())
            .join("resource.lib");
        assert!(resource.is_file(), "Tauri Windows resource was not generated");
        println!("cargo:rustc-link-arg-examples={}", resource.display());
    }
}
