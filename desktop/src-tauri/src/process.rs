use log::{debug, error, info};
use std::collections::HashMap;
use std::process::Child;

pub struct BackgroundProcessesGuard {
    processes: Vec<Child>,
}

impl BackgroundProcessesGuard {
    pub const fn new() -> Self {
        Self {
            processes: Vec::new(),
        }
    }

    pub fn add_process(&mut self, child: Child) {
        debug!("添加后台进程");
        self.processes.push(child);
    }

    pub fn kill_all_processes(&mut self) {
        info!("开始关闭所有后台进程");
        for child in self.processes.iter_mut() {
            if let Err(e) = child.kill() {
                error!("无法终止进程: {}", e);
            }
            let _ = child.wait();
        }
        self.processes.clear();
        info!("所有后台进程已关闭");
    }
}

// 存储特定类型进程的Child对象
pub struct ProcessManager {
    processes: HashMap<String, Child>,
}

impl ProcessManager {
    pub fn new() -> Self {
        Self {
            processes: HashMap::new(),
        }
    }

    pub fn add_process(&mut self, process_type: &str, mut child: Child) -> Result<(), String> {
        debug!("添加进程: {}", process_type);
        if self.is_process_running(process_type) && !self.kill_process(process_type) {
            let _ = child.kill(); let _ = child.wait();
            return Err(format!("无法替换进程: {}", process_type));
        }
        self.processes.insert(process_type.to_string(), child);
        Ok(())
    }

    pub fn is_process_running(&mut self, process_type: &str) -> bool {
        if let Some(child) = self.processes.get_mut(process_type) {
            // 尝试等待进程，但不阻塞
            match child.try_wait() {
                Ok(Some(_)) => {
                    // 进程已退出，从管理器中移除
                    info!("进程 {} 已终止", process_type);
                    self.processes.remove(process_type);
                    false
                }
                Ok(None) => {
                    // 进程仍在运行
                    true
                }
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

    pub fn kill_process(&mut self, process_type: &str) -> bool {
        if let Some(child) = self.processes.get_mut(process_type) {
            if let Err(e) = child.kill() {
                eprintln!("无法终止进程 {}: {}", process_type, e);
                return false;
            }
            if let Err(e) = child.wait() {
                error!("无法回收进程 {}: {}", process_type, e);
                return false;
            }
            self.processes.remove(process_type);
            true
        } else {
            false
        }
    }

    pub fn kill_all_processes(&mut self) {
        info!("开始关闭所有特定类型进程");
        for (process_type, child) in self.processes.iter_mut() {
            if let Err(e) = child.kill() {
                error!("无法终止进程 {}: {}", process_type, e);
            } else {
                info!("进程 {} 已终止", process_type);
            }
            let _ = child.wait();
        }
        self.processes.clear();
        info!("所有特定类型进程已关闭");
    }
}


// 获取进程PID
impl ProcessManager {
    pub fn get_process_pid(&self, process_type: &str) -> Option<String> {
        debug!("获取进程 {} 的PID", process_type);
        self.processes
            .get(process_type)
            .map(|child| child.id().to_string())
    }
}


impl Drop for ProcessManager {
    fn drop(&mut self) { self.kill_all_processes(); }
}
impl Drop for BackgroundProcessesGuard {
    fn drop(&mut self) { self.kill_all_processes(); }
}

#[cfg(test)]
#[path = "process_tests.rs"]
mod tests;
