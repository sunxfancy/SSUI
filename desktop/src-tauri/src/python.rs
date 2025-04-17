use std::process::Command;
use std::fs::File;
use std::io::Write;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::Serialize;
use std::sync::Mutex;
use lazy_static::lazy_static;
use std::process::Child;
use std::collections::HashMap;

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

// 存储特定类型进程的Child对象
pub struct ProcessManager {
    processes: Mutex<HashMap<String, Child>>
}

impl ProcessManager {
    pub fn new() -> Self {
        Self {
            processes: Mutex::new(HashMap::new())
        }
    }

    pub fn add_process(&self, process_type: &str, child: Child) {
        let mut processes = self.processes.lock().unwrap();
        processes.insert(process_type.to_string(), child);
    }

    pub fn get_process(&self, process_type: &str) -> Option<Child> {
        let mut processes = self.processes.lock().unwrap();
        processes.remove(process_type)
    }

    pub fn is_process_running(&self, process_type: &str) -> bool {
        let mut processes = self.processes.lock().unwrap();
        if let Some(child) = processes.get_mut(process_type) {
            // 尝试等待进程，但不阻塞
            match child.try_wait() {
                Ok(Some(_)) => {
                    // 进程已退出，从管理器中移除
                    processes.remove(process_type);
                    false
                },
                Ok(None) => {
                    // 进程仍在运行
                    true
                },
                Err(_) => {
                    // 发生错误，假设进程仍在运行
                    true
                }
            }
        } else {
            // 进程不存在
            false
        }
    }

    pub fn kill_process(&self, process_type: &str) -> bool {
        let mut processes = self.processes.lock().unwrap();
        if let Some(child) = processes.get_mut(process_type) {
            if let Err(e) = child.kill() {
                eprintln!("无法终止进程 {}: {}", process_type, e);
                return false;
            }
            processes.remove(process_type);
            true
        } else {
            false
        }
    }

    pub fn kill_all_processes(&self) {
        println!("开始关闭特定类型进程");
        let mut processes = self.processes.lock().unwrap();
        for (process_type, child) in processes.iter_mut() {
            if let Err(e) = child.kill() {
                eprintln!("无法终止进程 {}: {}", process_type, e);
            }
        }
        processes.clear();
    }
}

lazy_static! {
    pub static ref PROCESSES_GUARD: BackgroundProcessesGuard = BackgroundProcessesGuard::new();
    pub static ref PROCESS_MANAGER: ProcessManager = ProcessManager::new();
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

#[derive(Serialize)]
pub struct ProcessStatus {
    is_running: bool,
    pid: Option<String>
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

// 启动服务器
#[tauri::command]
pub async fn start_server(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    // 检查服务器是否已经运行
    if PROCESS_MANAGER.is_process_running("server") {
        // 获取进程ID
        let pid = PROCESS_MANAGER.get_process_pid("server")
            .ok_or_else(|| "无法获取服务器进程ID".to_string())?;
        return Ok(PythonCommand { pid });
    }
    
    // 启动服务器
    let args = vec!["-m", "server"];
    let child = spawn_python_process(path, cwd, args).await?;
    
    // 记录服务器进程
    let pid = child.id().to_string();
    PROCESS_MANAGER.add_process("server", child);
    
    Ok(PythonCommand { pid })
}

// 启动执行器
#[tauri::command]
pub async fn start_executor(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    // 检查执行器是否已经运行
    if PROCESS_MANAGER.is_process_running("executor") {
        // 获取进程ID
        let pid = PROCESS_MANAGER.get_process_pid("executor")
            .ok_or_else(|| "无法获取执行器进程ID".to_string())?;
        return Ok(PythonCommand { pid });
    }
    
    // 启动执行器
    let args = vec!["-m", "ss_executor"];
    let child = spawn_python_process(path, cwd, args).await?;
    
    // 记录执行器进程
    let pid = child.id().to_string();
    PROCESS_MANAGER.add_process("executor", child);
    
    Ok(PythonCommand { pid })
}

// 查询服务器状态
#[tauri::command]
pub async fn get_server_status() -> Result<ProcessStatus, String> {
    let is_running = PROCESS_MANAGER.is_process_running("server");
    let pid = if is_running {
        PROCESS_MANAGER.get_process_pid("server")
    } else {
        None
    };
    
    Ok(ProcessStatus {
        is_running,
        pid
    })
}

// 查询执行器状态
#[tauri::command]
pub async fn get_executor_status() -> Result<ProcessStatus, String> {
    let is_running = PROCESS_MANAGER.is_process_running("executor");
    let pid = if is_running {
        PROCESS_MANAGER.get_process_pid("executor")
    } else {
        None
    };
    
    Ok(ProcessStatus {
        is_running,
        pid
    })
}

// 获取进程PID
impl ProcessManager {
    pub fn get_process_pid(&self, process_type: &str) -> Option<String> {
        let processes = self.processes.lock().unwrap();
        processes.get(process_type).map(|child| child.id().to_string())
    }
}

// 启动Python进程并返回Child对象
async fn spawn_python_process(path: &str, cwd: &str, args: Vec<&str>) -> Result<Child, String> {
    // 从参数中提取一个标识符，用于日志文件名
    let args_identifier = if !args.is_empty() {
        // 使用第二个参数作为标识符的一部分
        args[1].replace(|c: char| !c.is_alphanumeric(), "_")
    } else {
        "no_args".to_string()
    };
    
    // 创建唯一的日志文件名
    let log_filename = format!("python_bg_{}.log", args_identifier);
    let error_log_filename = format!("python_bg_{}_error.log", args_identifier);

    let log_dir = std::path::Path::new(cwd).join("log");
    if !log_dir.exists() {
        std::fs::create_dir_all(&log_dir).map_err(|e| format!("无法创建日志目录: {}", e))?;
    }
    let log_path = log_dir.clone().join(&log_filename);
    let error_log_path = log_dir.join(&error_log_filename);
    
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
    
    Ok(child)
}

#[tauri::command]
pub async fn get_dev_root() -> Result<String, String>  {
    let current_dir: std::path::PathBuf = std::env::current_dir().map_err(|e| e.to_string())?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    Ok(current_dir.to_string_lossy().into_owned())
}