use std::process::Command;
use std::fs::File;
use std::io::Write;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::Serialize;
use std::sync::Mutex;
use lazy_static::lazy_static;
use std::process::Child;

pub struct BackgroundProcessesGuard {
    processes: Mutex<Vec<Child>>
}

impl BackgroundProcessesGuard {
    pub fn new() -> Self {
        Self {
            processes: Mutex::new(Vec::new())
        }
    }

    pub fn add_process(&self, child: Child) {
        self.processes.lock().unwrap().push(child);
    }

    pub fn kill_all_processes(&self) {
        println!("开始关闭后台进程");
        let mut processes = self.processes.lock().unwrap();
        for child in processes.iter_mut() {
            if let Err(e) = child.kill() {
                eprintln!("无法终止进程: {}", e);
            }
        }
        processes.clear();
    }
}

lazy_static! {
    pub static ref PROCESSES_GUARD: BackgroundProcessesGuard = BackgroundProcessesGuard::new();
}

#[tauri::command]
pub async fn run_python(path: &str, cwd: &str, args: Vec<&str>) -> Result<String, String> {
    let output = Command::new(path)
        .args(args.clone())
        .current_dir(cwd)
        .output()
        .expect(format!("failed to execute process, path: {}, cwd: {}, args: {:?}", path, cwd, args).as_str());

    let stdout = String::from_utf8(output.stdout).expect("failed to convert stdout to string");
    let stderr = String::from_utf8(output.stderr).expect("failed to convert stderr to string");
    if output.status.success() {
        Ok(stdout)
    } else {
        Err(stderr)
    }
}
#[derive(Serialize)]
pub struct PythonCommand {
    pid: String
}

#[tauri::command]
pub async fn run_python_background(path: &str, cwd: &str, args: Vec<&str>) -> Result<PythonCommand, String> {
    // 生成唯一的日志文件名，使用时间戳和进程参数
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| format!("无法获取时间戳: {}", e))?
        .as_secs();
    
    // 从参数中提取一个标识符，用于日志文件名
    let args_identifier = if !args.is_empty() {
        // 使用第二个参数作为标识符的一部分
        args[1].replace(|c: char| !c.is_alphanumeric(), "_")
    } else {
        "no_args".to_string()
    };
    
    // 创建唯一的日志文件名
    let log_filename = format!("python_bg_{}_{}.log", args_identifier, timestamp);
    let error_log_filename = format!("python_bg_{}_{}_error.log", args_identifier, timestamp);
    
    let log_path = std::path::Path::new(cwd).join(&log_filename);
    let error_log_path = std::path::Path::new(cwd).join(&error_log_filename);
    
    let log_file = File::create(&log_path)
        .map_err(|e| format!("无法创建日志文件: {}", e))?;
    
    let error_log_file = File::create(&error_log_path)
        .map_err(|e| format!("无法创建错误日志文件: {}", e))?;
    
    let child = Command::new(path)
        .args(args.clone())
        .current_dir(cwd)
        .stdout(log_file)
        .stderr(error_log_file)
        .spawn()
        .map_err(|e| format!("无法启动进程: {}", e))?;

    let pid = child.id().to_string();
    // 将子进程添加到全局列表中
    PROCESSES_GUARD.add_process(child);

    // 返回进程ID
    Ok(PythonCommand { pid })
}




#[tauri::command]
pub async fn get_dev_root() -> Result<String, String>  {
    let current_dir: std::path::PathBuf = std::env::current_dir().map_err(|e| e.to_string())?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    Ok(current_dir.to_string_lossy().into_owned())
}