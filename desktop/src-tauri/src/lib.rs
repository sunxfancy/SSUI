use downloader::download_python;
use downloader::unpack_app;
use downloader::set_proxy;
use gpu_detector::detect_gpu;
use python::run_python;
use python::run_python_background;
use python::get_dev_root;
use python::start_server;
use python::start_executor;
use python::get_server_status;
use python::get_executor_status;
use python::PROCESSES_GUARD;
use python::PROCESS_MANAGER;
use std::env;
mod gpu_detector;
mod downloader;
mod python;


#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 初始化日志系统
    #[cfg(debug_assertions)]
    if env::var("RUST_LOG").is_err() {
        env::set_var("RUST_LOG", "info")
    }

    env_logger::init();
    log::info!("应用程序启动");
    
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_window_state::Builder::new().build())
        .plugin(tauri_plugin_websocket::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        // .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_upload::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            get_dev_root, 
            download_python, 
            detect_gpu, 
            run_python,
            run_python_background, 
            unpack_app,
            start_server,
            start_executor,
            get_server_status,
            get_executor_status,
            set_proxy
        ])
        .setup(|app| {
            log::info!("应用程序设置完成");
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application");
    
    app.run(move |_app_handle, _event| {
        match _event {
            tauri::RunEvent::Exit => {
                log::info!("应用程序退出，清理资源");
                // 关闭所有后台进程
                PROCESSES_GUARD.kill_all_processes();
                // 关闭特定类型进程
                PROCESS_MANAGER.kill_all_processes();
            }
            _ => {}
        }
    });
}
