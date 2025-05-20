use downloader::{
    download_python,
    unpack_app,
    set_proxy,
    create_download_task,
    pause_download_task,
    resume_download_task,
    cancel_download_task,
    get_download_task_list,
    get_download_task_progress
};
use gpu_detector::detect_gpu;
use python::{
    run_python,
    run_python_background,
    get_dev_root,
    start_server,
    start_executor,
    restart_server,
    restart_executor,
    get_server_status,
    get_executor_status,
    GLOBAL_PROCESS_STATE,
};
use std::env;

mod gpu_detector;
mod downloader;
mod python;
mod hf_transfer;

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
            restart_server,
            restart_executor,
            set_proxy,

            create_download_task,
            pause_download_task,
            resume_download_task,
            cancel_download_task,
            get_download_task_list,
            get_download_task_progress
        ])
        .setup(|_app: &mut tauri::App| {
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
                GLOBAL_PROCESS_STATE.processes_guard().kill_all_processes();
                // 关闭特定类型进程
                GLOBAL_PROCESS_STATE.process_manager().kill_all_processes();
            }
            _ => {}
        }
    });
}
