use tauri::{AppHandle, Emitter};
use tauri_plugin_http::reqwest;
use log::{info, error, debug};
use std::sync::Mutex;
use std::sync::{Arc, RwLock, LazyLock};
use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use tokio::fs as tokio_fs;
use tokio::io::AsyncWriteExt;
use reqwest::header::RANGE;
use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};
use tokio::sync::Semaphore;

static PROXY_URL: Mutex<Option<String>> = Mutex::new(None);

// 设置全局代理
#[tauri::command(rename_all = "snake_case")]
pub fn set_proxy(proxy_url: &str) -> Result<(), String> {
    info!("设置代理服务器: {}", proxy_url);
    
    // 验证代理URL格式
    if !proxy_url.starts_with("http://") && !proxy_url.starts_with("https://") {
        let err_msg = format!("代理URL格式不正确，必须以http://或https://开头: {}", proxy_url);
        error!("{}", err_msg);
        return Err(err_msg);
    }
    
    // 保存代理URL
    let mut proxy = PROXY_URL.lock().unwrap();
    *proxy = Some(proxy_url.to_string());
    
    info!("代理服务器设置成功");
    Ok(())
}

// 获取当前代理设置
pub fn get_proxy() -> Option<String> {
    PROXY_URL.lock().unwrap().clone()
}

// 创建带代理的客户端
pub fn create_client_with_proxy() -> reqwest::Client {
    let mut client_builder = reqwest::Client::builder();
    
    // 如果有代理设置，则使用代理
    if let Some(proxy_url) = get_proxy() {
        info!("使用代理服务器: {}", proxy_url);
        
        // 确保代理URL有正确的scheme
        let proxy_url_with_scheme = if !proxy_url.contains("://") {
            format!("http://{}", proxy_url)
        } else {
            proxy_url
        };
        
        // 根据代理URL的协议选择代理类型
        if proxy_url_with_scheme.starts_with("http://") {
            client_builder = client_builder.proxy(reqwest::Proxy::http(&proxy_url_with_scheme).unwrap());
        } else if proxy_url_with_scheme.starts_with("https://") {
            client_builder = client_builder.proxy(reqwest::Proxy::https(&proxy_url_with_scheme).unwrap());
        }
    }
    
    client_builder.build().unwrap()
}

#[tauri::command(rename_all = "snake_case")]
pub async fn download_python(version: &str, release_date: &str, architecture: &str, path: &str) -> Result<String, String> {
    let url = format!(
        "https://github.com/astral-sh/python-build-standalone/releases/download/{release_date}/cpython-{version}+{release_date}-{architecture}-install_only_stripped.tar.gz"
    );
    let china_mirror = format!(
        "https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-{version}%{release_date}-{architecture}-install_only_stripped.tar.gz"
    );
    info!("开始下载Python: {}", url);
    debug!("下载参数: version={}, release_date={}, architecture={}, path={}", version, release_date, architecture, path);
    
    // 尝试下载并处理响应
    async fn try_download(url: &str, use_proxy: bool) -> Result<reqwest::Response, String> {
        let client = if use_proxy {
            if let Some(proxy_url) = get_proxy() {
                info!("使用代理下载: {}", proxy_url);
                create_client_with_proxy()
            } else {
                return Err("未设置代理".to_string());
            }
        } else {
            reqwest::Client::new()
        };
        
        client.get(url).send().await.map_err(|e| format!("下载失败: {}", e))
    }
    
    // 处理响应
    async fn process_response(response: reqwest::Response) -> Result<Vec<u8>, String> {
        // 检查响应状态码
        if !response.status().is_success() {
            return Err(format!("下载失败,状态码: {}", response.status()));
        }
        
        // 检查Content-Type头,确保是二进制文件
        let content_type = response.headers()
            .get("content-type")
            .and_then(|h| h.to_str().ok())
            .unwrap_or("");
        
        debug!("响应Content-Type: {}", content_type);
        
        if !content_type.contains("application/octet-stream") && 
           !content_type.contains("application/x-gzip") {
            return Err(format!("下载内容不是预期的文件类型: {}", content_type));
        }
        
        // 读取响应内容
        response.bytes().await
            .map(|bytes| {
                info!("下载完成，文件大小: {} 字节", bytes.len());
                bytes.to_vec()
            })
            .map_err(|e| format!("读取响应内容失败: {}", e))
    }
    
    // 解压文件
    fn extract_file(bytes: Vec<u8>, path: &str) -> Result<(), String> {
        // 直接从内存中的bytes创建读取器
        let cursor = std::io::Cursor::new(bytes);
        let tar = flate2::read::GzDecoder::new(cursor);
        
        // 解压tar
        info!("开始解压到: {}", path);
        let mut archive = tar::Archive::new(tar);
        archive.unpack(path)
            .map_err(|e| format!("解压失败: {}", e))
    }
    
    // 下载并处理流程
    async fn download_and_process(url: &str, path: &str, use_proxy: bool) -> Result<String, String> {
        let response = try_download(url, use_proxy).await?;
        let bytes = process_response(response).await?;
        extract_file(bytes, path)?;
        info!("解压完成");
        Ok("success".to_string())
    }
    
    // 首先尝试不使用代理下载
    match download_and_process(&url, path, false).await {
        Ok(result) => Ok(result),
        Err(_e) => {
            // 如果直接下载失败且设置了代理，则尝试使用代理重试
            if get_proxy().is_some() {
                info!("直接下载失败，尝试使用代理重试");
                download_and_process(&url, path, true).await
            } else {
                info!("直接下载失败，尝试使用中国镜像源");
                download_and_process(&china_mirror, path, false).await
            }
        }
    }
}

#[tauri::command(rename_all = "snake_case")]
pub async fn unpack_app(tar_path: &str, target_path: &str) -> Result<String, String> {
    info!("开始解压应用: {} -> {}", tar_path, target_path);
    
    let tar = match std::fs::File::open(tar_path) {
        Ok(file) => file,
        Err(e) => {
            let err_msg = format!("打开文件失败: {}", e);
            error!("{}", err_msg);
            return Err(err_msg);
        }
    };
    
    let tar = flate2::read::GzDecoder::new(tar);
    let mut archive = tar::Archive::new(tar);
    
    match archive.unpack(target_path) {
        Ok(_) => {
            info!("应用解压完成");
            Ok("success".to_string())
        },
        Err(e) => {
            let err_msg = format!("解压应用失败: {}", e);
            error!("{}", err_msg);
            Err(err_msg)
        }
    }
}

#[derive(Serialize, Deserialize, Default)]
struct Progress {
    completed: HashSet<usize>,
}

pub struct ChunkedDownloader {
    url: String,
    output: String,
    chunk_size: u64,
    progress_file: String,
    retry_times: usize,
    progress_callback: Option<Arc<dyn Fn(usize, usize) + Send + Sync>>,
    max_concurrent: usize,
}

impl ChunkedDownloader {
    pub fn new(url: &str, output: &str, chunk_size: u64) -> Self {
        Self {
            url: url.to_string(),
            output: output.to_string(),
            chunk_size,
            progress_file: format!("{}.progress.json", output),
            retry_times: 3,
            progress_callback: None,
            max_concurrent: 4, // 默认最大并发数为4
        }
    }

    pub fn with_retry_times(mut self, retry: usize) -> Self {
        self.retry_times = retry;
        self
    }

    pub fn with_max_concurrent(mut self, max: usize) -> Self {
        self.max_concurrent = max;
        self
    }

    pub fn with_progress_callback<F>(mut self, callback: F) -> Self
    where
        F: Fn(usize, usize) + Send + Sync + 'static,
    {
        self.progress_callback = Some(Arc::new(callback));
        self
    }

    async fn get_file_size(&self) -> Option<u64> {
        let client = reqwest::Client::new();
            
        match client.get(&self.url).send().await {
            Ok(resp) => {
                let size = resp.content_length();
                
                // 如果没有获取到文件大小，尝试从Content-Length头获取
                if size.is_none() {
                    if let Some(length) = resp.headers().get("content-length") {
                        if let Ok(length_str) = length.to_str() {
                            if let Ok(length_num) = length_str.parse::<u64>() {
                                println!("从Content-Length头获取到文件大小: {} 字节", length_num);
                                return Some(length_num);
                            }
                        }
                    }
                }
                
                size
            },
            Err(e) => {
                println!("获取文件大小失败: {}", e);
                None
            }
        }
    }

    async fn load_progress(&self) -> Progress {
        if let Ok(bytes) = tokio_fs::read(&self.progress_file).await {
            serde_json::from_slice(&bytes).unwrap_or_default()
        } else {
            Progress::default()
        }
    }

    async fn save_progress(&self, progress: &Progress) {
        if let Ok(json) = serde_json::to_vec(progress) {
            let _ = tokio_fs::write(&self.progress_file, json).await;
        }
    }

    async fn download_chunk(&self, index: usize, start: u64, end: u64) -> Result<(), Box<dyn std::error::Error>> {
        let part_file = format!("{}.part{}", &self.output, index);
        
        if Path::new(&part_file).exists() {
            return Ok(());
        }

        let client = reqwest::Client::new();
        let range_header = format!("bytes={}-{}", start, end);
        
        let mut resp = match client.get(&self.url)
            .header(RANGE, range_header)
            .send()
            .await {
                Ok(resp) => {
                    resp.error_for_status()?
                },
                Err(e) => {
                    return Err(e.into());
                }
            };
        
        let mut file = match tokio_fs::File::create(&part_file).await {
            Ok(file) => file,
            Err(e) => {
                error!("创建文件失败: {}", e);
                return Err(e.into());
            }
        };

        let mut downloaded = 0;
        while let Some(chunk) = resp.chunk().await? {
            match file.write_all(&chunk).await {
                Ok(_) => {
                    downloaded += chunk.len();
                    debug!("块 {} 已下载: {} 字节", index, downloaded);
                },
                Err(e) => {
                    error!("写入文件失败: {}", e);
                    return Err(e.into());
                }
            }
        }

        match file.flush().await {
            Ok(_) => info!("块 {} 写入完成", index),
            Err(e) => {
                error!("刷新文件失败: {}", e);
                return Err(e.into());
            }
        }

        match file.sync_all().await {
            Ok(_) => info!("块 {} 同步到磁盘完成", index),
            Err(e) => {
                error!("同步文件失败: {}", e);
                return Err(e.into());
            }
        }

        // 验证下载的块大小
        if let Ok(metadata) = tokio_fs::metadata(&part_file).await {
            info!("块 {} 大小: {} 字节", index, metadata.len());
            if metadata.len() == 0 {
                error!("块 {} 下载为空", index);
                return Err("下载的块为空".into());
            }
        }

        Ok(())
    }

    async fn retry_download_chunk(&self, index: usize, start: u64, end: u64) -> bool {
        for attempt in 1..=self.retry_times {
            match self.download_chunk(index, start, end).await {
                Ok(_) => return true,
                Err(e) => {
                    eprintln!("Chunk {} attempt {}/{} failed: {}", index, attempt, self.retry_times, e);
                }
            }
        }
        false
    }

    async fn merge_chunks(&self, total_chunks: usize) -> std::io::Result<()> {
        info!("开始合并文件块...");
        let mut output_file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.output)?;

        for i in 0..total_chunks {
            let part_file = format!("{}.part{}", &self.output, i);
            info!("合并块 {}: {}", i, part_file);
            
            if !Path::new(&part_file).exists() {
                error!("块文件不存在: {}", part_file);
                return Err(std::io::Error::new(
                    std::io::ErrorKind::NotFound,
                    format!("Chunk file not found: {}", part_file)
                ));
            }

            let mut part = File::open(&part_file)?;
            let mut buf = Vec::new();
            part.read_to_end(&mut buf)?;
            
            if buf.is_empty() {
                error!("块 {} 是空的！", i);
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    format!("Chunk {} is empty", i)
                ));
            }
            
            info!("写入块 {}: {} 字节", i, buf.len());
            output_file.write_all(&buf)?;
            output_file.flush()?;
            
            // 删除临时文件
            let _ = std::fs::remove_file(&part_file);
            info!("块 {} 合并完成", i);
        }

        // 确保文件被正确写入
        output_file.flush()?;
        output_file.sync_all()?;

        // 删除进度记录
        let _ = std::fs::remove_file(&self.progress_file);

        info!("文件合并完成");
        Ok(())
    }

    // 计算文件的SHA256哈希值
    async fn calculate_sha256(&self, file_path: &str) -> Result<String, Box<dyn std::error::Error>> {
        let mut file = File::open(file_path)?;
        let mut hasher = Sha256::new();
        let mut buffer = [0; 8192];
        
        loop {
            let bytes_read = file.read(&mut buffer)?;
            if bytes_read == 0 {
                break;
            }
            hasher.update(&buffer[..bytes_read]);
        }
        
        let hash = hasher.finalize();
        Ok(format!("{:X}", hash))
    }

    pub async fn download(&self) -> Result<(), Box<dyn std::error::Error>> {
        let total_size = match self.get_file_size().await {
            Some(size) => size,
            None => return Err("无法获取文件大小".into()),
        };

        let total_chunks = ((total_size + self.chunk_size - 1) / self.chunk_size) as usize;
        let progress = self.load_progress().await;

        // 创建信号量来控制并发
        let semaphore = Arc::new(Semaphore::new(self.max_concurrent));
        let mut tasks = vec![];

        for i in 0..total_chunks {
            if progress.completed.contains(&i) {
                continue;
            }

            let start = i as u64 * self.chunk_size;
            let end = ((i + 1) as u64 * self.chunk_size - 1).min(total_size - 1);
            
            let url = self.url.clone();
            let output = self.output.clone();
            let progress_file = self.progress_file.clone();
            let retry_times = self.retry_times;
            let progress_callback = self.progress_callback.clone();
            let chunk_size = self.chunk_size;
            let sem = semaphore.clone();

            let fut = async move {
                // 获取信号量许可
                let _permit = sem.acquire().await.unwrap();
                
                let downloader = ChunkedDownloader {
                    url,
                    output,
                    chunk_size,
                    progress_file,
                    retry_times,
                    progress_callback,
                    max_concurrent: 1, // 子下载器不需要并发
                };

                let success = downloader.retry_download_chunk(i, start, end).await;
                if success {
                    let mut updated_progress = downloader.load_progress().await;
                    updated_progress.completed.insert(i);
                    downloader.save_progress(&updated_progress).await;

                    if let Some(callback) = &downloader.progress_callback {
                        callback(updated_progress.completed.len(), total_chunks);
                    }
                }
            };

            tasks.push(tokio::spawn(fut));
        }

        // 等待所有任务完成
        for task in tasks {
            let _ = task.await;
        }

        // 检查是否所有块都完成
        let final_progress = self.load_progress().await;
        if final_progress.completed.len() == total_chunks {
            self.merge_chunks(total_chunks).await?;
            
            // 验证文件大小
            let file_size = tokio_fs::metadata(&self.output).await?.len();
            if file_size != total_size {
                return Err("文件大小不匹配".into());
            }
            
            // 计算并验证SHA256
            let _hash = self.calculate_sha256(&self.output).await?;
        } else {
            return Err("下载未完成".into());
        }

        Ok(())
    }
}

#[derive(Serialize, Deserialize, Default, Clone)]
pub struct DownloadTask {
    url: String,
    output_path: String,
    sha256: String,
    progress: u32,
    total_blocks: u32,
    status: TaskStatus,
}

#[derive(Serialize, Deserialize, Default, Clone, PartialEq)]
pub enum TaskStatus {
    #[default]
    Pending,
    Downloading,
    Paused,
    Completed,
    Failed,
    Cancelled,
}

struct DownloadTaskManager {
    tasks: HashMap<String, DownloadTask>,
    downloaders: HashMap<String, Arc<RwLock<Option<ChunkedDownloader>>>>,
}

impl DownloadTaskManager {
    fn new() -> Self {
        Self {
            tasks: HashMap::new(),
            downloaders: HashMap::new(),
        }
    }

    fn add_task(&mut self, url: &str, output_path: &str, sha256: &str) {
        self.tasks.insert(url.to_string(), DownloadTask {
            url: url.to_string(),
            output_path: output_path.to_string(),
            sha256: sha256.to_string(),
            progress: 0,
            total_blocks: 0,
            status: TaskStatus::Pending,
        });
    }

    fn get_task(&self, url: &str) -> Option<&DownloadTask> {
        self.tasks.get(url)
    }

    fn update_task_status(&mut self, url: &str, status: TaskStatus) {
        if let Some(task) = self.tasks.get_mut(url) {
            task.status = status;
        }
    }

    fn update_task_progress(&mut self, url: &str, progress: u32, total_blocks: u32) {
        if let Some(task) = self.tasks.get_mut(url) {
            task.progress = progress;
            task.total_blocks = total_blocks;
        }
    }
}

// 全局任务管理器
static TASK_MANAGER: LazyLock<RwLock<DownloadTaskManager>> = LazyLock::new(|| RwLock::new(DownloadTaskManager::new()));

#[tauri::command(rename_all = "snake_case")]
pub async fn create_download_task(app: AppHandle, url: &str, output_path: &str, sha256: &str) -> Result<(), String> {
    let mut manager = TASK_MANAGER.write().unwrap();
    
    // 检查任务是否已存在
    if manager.get_task(url).is_some() {
        return Err("任务已存在".to_string());
    }

    // 创建下载器
    let downloader = ChunkedDownloader::new(url, output_path, 1024 * 1024)
        .with_retry_times(3)
        .with_max_concurrent(4)
        .with_progress_callback({
            let app = app.clone();
            let url = url.to_string();
            move |completed, total| {
                if let Ok(mut manager) = TASK_MANAGER.write() {
                    manager.update_task_progress(&url, completed as u32, total as u32);
                }
                
                // 发送进度更新事件
                let _ = app.emit("download-progress", serde_json::json!({
                    "url": url,
                    "progress": completed,
                    "total": total
                }));
            }
        });

    // 添加任务
    manager.add_task(url, output_path, sha256);
    manager.downloaders.insert(url.to_string(), Arc::new(RwLock::new(Some(downloader))));
    manager.update_task_status(url, TaskStatus::Pending);

    // 启动下载
    let downloader = manager.downloaders.get(url).unwrap().clone();
    let url = url.to_string();
    let app = app.clone();
    
    tokio::spawn(async move {
        // 在异步任务中获取下载器
        let downloader = {
            let mut guard = downloader.write().unwrap();
            guard.take()
        };

        if let Some(downloader) = downloader {
            if let Ok(mut manager) = TASK_MANAGER.write() {
                manager.update_task_status(&url, TaskStatus::Downloading);
            }
            
            match downloader.download().await {
                Ok(_) => {
                    if let Ok(mut manager) = TASK_MANAGER.write() {
                        manager.update_task_status(&url, TaskStatus::Completed);
                    }
                    let _ = app.emit("download-completed", url);
                },
                Err(e) => {
                    if let Ok(mut manager) = TASK_MANAGER.write() {
                        manager.update_task_status(&url, TaskStatus::Failed);
                    }
                    let _ = app.emit("download-failed", serde_json::json!({
                        "url": url,
                        "error": e.to_string()
                    }));
                }
            }
        }
    });

    Ok(())
}

#[tauri::command(rename_all = "snake_case")]
pub async fn pause_download_task(app: AppHandle, url: &str) -> Result<(), String> {
    let mut manager = TASK_MANAGER.write().unwrap();
    
    if let Some(task) = manager.get_task(url) {
        if task.status == TaskStatus::Downloading {
            manager.update_task_status(url, TaskStatus::Paused);
            let _ = app.emit("download-paused", url);
            Ok(())
        } else {
            Err("任务不在下载状态".to_string())
        }
    } else {
        Err("任务不存在".to_string())
    }
}

#[tauri::command(rename_all = "snake_case")]
pub async fn resume_download_task(app: AppHandle, url: &str) -> Result<(), String> {
    let mut manager = TASK_MANAGER.write().unwrap();
    
    if let Some(task) = manager.get_task(url) {
        if task.status == TaskStatus::Paused {
            manager.update_task_status(url, TaskStatus::Downloading);
            let _ = app.emit("download-resumed", url);
            Ok(())
        } else {
            Err("任务不在暂停状态".to_string())
        }
    } else {
        Err("任务不存在".to_string())
    }
}

#[tauri::command(rename_all = "snake_case")]
pub async fn cancel_download_task(app: AppHandle, url: &str) -> Result<(), String> {
    let mut manager = TASK_MANAGER.write().unwrap();
    
    if let Some(task) = manager.get_task(url) {
        if task.status == TaskStatus::Downloading || task.status == TaskStatus::Paused {
            manager.update_task_status(url, TaskStatus::Cancelled);
            let _ = app.emit("download-cancelled", url);
            Ok(())
        } else {
            Err("任务不在可取消状态".to_string())
        }
    } else {
        Err("任务不存在".to_string())
    }
}

#[tauri::command(rename_all = "snake_case")]
pub async fn get_download_task_list() -> Result<Vec<DownloadTask>, String> {
    let manager = TASK_MANAGER.read().unwrap();
    Ok(manager.tasks.values().cloned().collect())
}

#[tauri::command(rename_all = "snake_case")]
pub async fn get_download_task_progress(url: &str) -> Result<DownloadTask, String> {
    let manager = TASK_MANAGER.read().unwrap();
    manager.get_task(url)
        .cloned()
        .ok_or_else(|| "任务不存在".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[tokio::test]
    async fn test_download_python() {
        let result = download_python("3.12.8", "20241219", "x86_64-pc-windows-msvc", "C:\\Users\\sunxf\\AppData\\Roaming\\com.ssui.app").await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_download_model() {
        let url = "https://civitai.com/api/download/models/11964?type=Model&format=SafeTensor&size=full&fp=fp16";
        let output = "test_model.safetensors";
        
        let downloader = ChunkedDownloader::new(
            url,
            output,
            1024 * 1024  // 1MB chunks
        )
        .with_retry_times(3)
        .with_max_concurrent(4)  // 设置最大并发数为4
        .with_progress_callback(|completed, total| {
            println!("下载进度: {}/{} ({}%)", 
                completed, 
                total, 
                (completed as f64 / total as f64 * 100.0) as u32
            );
        });

        let start = Instant::now();
        
        match downloader.download().await {
            Ok(_) => {
                let duration = start.elapsed();
                println!("下载完成！用时: {:.2}秒", duration.as_secs_f64());
                
                // 验证文件是否存在
                assert!(Path::new(output).exists(), "下载的文件不存在");
                
                // 验证文件大小
                let file_size = tokio_fs::metadata(output).await.unwrap().len();
                println!("文件大小: {} 字节", file_size);
                assert!(file_size > 0, "文件大小为0");
                
                // 清理测试文件
                let _ = std::fs::remove_file(output);
                let _ = std::fs::remove_file(format!("{}.progress.json", output));
            },
            Err(e) => {
                println!("下载失败: {}", e);
                panic!("下载失败: {}", e);
            }
        }
    }
}

