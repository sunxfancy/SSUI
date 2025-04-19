// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // 初始化日志系统
    env_logger::init();
    log::info!("应用程序启动");
    
    ssui_lib::run()
}
