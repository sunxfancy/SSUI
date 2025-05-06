use std::process::Command;
use std::fs::File;
use std::time::{SystemTime, UNIX_EPOCH};
use serde::Serialize;
use std::sync::Mutex;
use lazy_static::lazy_static;
use std::process::Child;
use std::collections::HashMap;
use log::{info, error, warn, debug};
#[cfg(windows)]
use std::os::windows::process::CommandExt; // 只在windows平台引入CommandExt
use crate::downloader::get_proxy;

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
        debug!("添加后台进程");
        self.processes.lock().unwrap().push(child);
    }

    pub fn kill_all_processes(&self) {
        info!("开始关闭所有后台进程");
        let mut processes = self.processes.lock().unwrap();
        for child in processes.iter_mut() {
            if let Err(e) = child.kill() {
                error!("无法终止进程: {}", e);
            }
        }
        processes.clear();
        info!("所有后台进程已关闭");
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
        debug!("添加进程: {}", process_type);
        self.processes.lock().unwrap().insert(process_type.to_string(), child);
    }

    pub fn is_process_running(&self, process_type: &str) -> bool {
        let mut processes = self.processes.lock().unwrap();
        if let Some(child) = processes.get_mut(process_type) {
            // 尝试等待进程，但不阻塞
            match child.try_wait() {
                Ok(Some(_)) => {
                    // 进程已退出，从管理器中移除
                    info!("进程 {} 已终止", process_type);
                    processes.remove(process_type);
                    false
                },
                Ok(None) => {
                    // 进程仍在运行
                    true
                },
                Err(e) => {
                    // 发生错误，假设进程仍在运行
                    error!("终止进程 {} 失败: {}", process_type, e);
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
        info!("开始关闭所有特定类型进程");
        let mut processes = self.processes.lock().unwrap();
        for (process_type, child) in processes.iter_mut() {
            if let Err(e) = child.kill() {
                error!("无法终止进程 {}: {}", process_type, e);
            } else {
                info!("进程 {} 已终止", process_type);
            }
        }
        processes.clear();
        info!("所有特定类型进程已关闭");
    }
}

lazy_static! {
    pub static ref PROCESSES_GUARD: BackgroundProcessesGuard = BackgroundProcessesGuard::new();
    pub static ref PROCESS_MANAGER: ProcessManager = ProcessManager::new();
}

fn set_proxy_for_python(cmd: &mut Command, proxy_url: &str) {
    info!("为Python进程设置代理: {}", proxy_url);
    
    // 确保代理URL有正确的scheme
    let proxy_url_with_scheme = if !proxy_url.contains("://") {
        format!("http://{}", proxy_url)
    } else {
        proxy_url.to_string()
    };
    
    // 根据代理URL的协议选择代理类型
    if proxy_url_with_scheme.starts_with("http://") {
        cmd.env("HTTP_PROXY", &proxy_url_with_scheme)
            .env("HTTPS_PROXY", &proxy_url_with_scheme);
    } else if proxy_url_with_scheme.starts_with("https://") {
        cmd.env("HTTPS_PROXY", &proxy_url_with_scheme);
    } 
    
    // 如果代理URL包含用户名和密码，则设置相应的环境变量
    if let Some(auth_start) = proxy_url_with_scheme.find('@') {
        if let Some(scheme_end) = proxy_url_with_scheme.find("://") {
            let auth_part = &proxy_url_with_scheme[scheme_end + 3..auth_start];
            if let Some(colon_pos) = auth_part.find(':') {
                let username = &auth_part[..colon_pos];
                let password = &auth_part[colon_pos + 1..];
                
                if proxy_url_with_scheme.starts_with("http://") {
                cmd.env("HTTP_PROXY_USERNAME", username)
                    .env("HTTP_PROXY_PASSWORD", password);
                } else if proxy_url_with_scheme.starts_with("https://") {
                    cmd.env("HTTPS_PROXY_USERNAME", username)
                    .env("HTTPS_PROXY_PASSWORD", password);
                }
            }
        }
    }
}

// 用来运行pip，所以要设置代理
#[tauri::command]
pub async fn run_python(path: &str, cwd: &str, args: Vec<&str>) -> Result<String, String> {
    info!("运行Python脚本: {} 在目录: {}", path, cwd);
    debug!("Python参数: {:?}", args);
    
    // 创建基本命令
    let create_cmd = |use_proxy: bool| -> Command {
        let mut cmd = Command::new(path);
        cmd.args(args.clone())
            .current_dir(cwd)
            .env("PYTHONIOENCODING", "utf-8");
        
        if use_proxy {
            if let Some(proxy_url) = get_proxy() {
                set_proxy_for_python(&mut cmd, &proxy_url);
            }
        }
        cmd
    };
    
    // 执行命令并处理结果
    fn run_and_process(mut cmd: Command, use_proxy: bool) -> Result<String, String> {
        let output = cmd.output()
            .map_err(|e| format!("{}执行进程失败: {}", if use_proxy { "使用代理" } else { "" }, e))?;
        
        let stdout = String::from_utf8(output.stdout).expect("无法将stdout转换为字符串");
        let stderr = String::from_utf8(output.stderr).expect("无法将stderr转换为字符串");
        
        if output.status.success() {
            info!("{}Python脚本执行成功", if use_proxy { "使用代理后" } else { "" });
            debug!("Python输出: {}", stdout);
            Ok(stdout)
        } else {
            let err_msg = format!("{}Python脚本执行失败: {}", if use_proxy { "使用代理后" } else { "" }, stderr);
            error!("{}", err_msg);
            Err(stderr)
        }
    }
    
    // 首先尝试不使用代理运行
    match run_and_process(create_cmd(false), false) {
        Ok(result) => Ok(result),
        Err(e) => {
            // 如果执行失败且设置了代理，则尝试使用代理重试
            if get_proxy().is_some() {
                info!("Python脚本执行失败，尝试使用代理重试");
                run_and_process(create_cmd(true), true)
            } else {
                Err(e)
            }
        }
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
    info!("在后台运行Python脚本: {} 在目录: {}", path, cwd);
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
    info!("后台Python进程已启动，PID: {}", pid);
    // 将子进程添加到全局列表中
    PROCESSES_GUARD.add_process(child);

    // 返回进程ID
    Ok(PythonCommand { pid })
}

// 启动服务器
#[tauri::command]
pub async fn start_server(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    info!("启动服务器: {} 在目录: {}", path, cwd);
    // 检查服务器是否已经运行
    if PROCESS_MANAGER.is_process_running("server") {
        warn!("服务器已经在运行中");
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
    info!("服务器进程已启动，PID: {}", pid);
    
    // 将进程添加到进程管理器
    PROCESS_MANAGER.add_process("server", child);
    
    Ok(PythonCommand { pid })
}

// 启动执行器
#[tauri::command]
pub async fn start_executor(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    info!("启动执行器: {} 在目录: {}", path, cwd);
    
    // 检查执行器是否已经在运行
    if PROCESS_MANAGER.is_process_running("executor") {
        warn!("执行器已经在运行中");
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
    info!("执行器进程已启动，PID: {}", pid);
    
    // 将进程添加到进程管理器
    PROCESS_MANAGER.add_process("executor", child);
    
    Ok(PythonCommand { pid })
}

// 重启服务器
#[tauri::command]
pub async fn restart_server(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    info!("重启服务器: {} 在目录: {}", path, cwd);
    
    // 先停止现有服务器进程
    if PROCESS_MANAGER.is_process_running("server") {
        info!("停止现有服务器进程");
        PROCESS_MANAGER.kill_process("server");
    }
    
    // 启动新的服务器进程
    let args = vec!["-m", "server"];
    let child = spawn_python_process(path, cwd, args).await?;
    
    // 记录服务器进程
    let pid = child.id().to_string();
    info!("服务器进程已重启，PID: {}", pid);
    
    // 将进程添加到进程管理器
    PROCESS_MANAGER.add_process("server", child);
    
    Ok(PythonCommand { pid })
}

// 重启执行器
#[tauri::command]
pub async fn restart_executor(path: &str, cwd: &str) -> Result<PythonCommand, String> {
    info!("重启执行器: {} 在目录: {}", path, cwd);
    
    // 先停止现有执行器进程
    if PROCESS_MANAGER.is_process_running("executor") {
        info!("停止现有执行器进程");
        PROCESS_MANAGER.kill_process("executor");
    }
    
    // 启动新的执行器进程
    let args = vec!["-m", "ss_executor"];
    let child = spawn_python_process(path, cwd, args).await?;
    
    // 记录执行器进程
    let pid = child.id().to_string();
    info!("执行器进程已重启，PID: {}", pid);
    
    // 将进程添加到进程管理器
    PROCESS_MANAGER.add_process("executor", child);
    
    Ok(PythonCommand { pid })
}


// 查询服务器状态
#[tauri::command]
pub async fn get_server_status() -> Result<ProcessStatus, String> {
    debug!("获取服务器状态");
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
    debug!("获取执行器状态");
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
        debug!("获取进程 {} 的PID", process_type);
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
    
    let mut cmd = Command::new(path);
    cmd.args(args.clone())
        .current_dir(cwd)
        .stdout(log_file)
        .stderr(error_log_file)
        .env("PYTHONIOENCODING", "utf-8");


    //在Windows上设置creation_flags 防治创建cmd窗口
    #[cfg(windows)]
    {
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    
    let child = cmd.spawn()
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