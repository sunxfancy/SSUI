use tauri_plugin_http::reqwest;
use log::{info, error, warn, debug};
use std::sync::Mutex;
use lazy_static::lazy_static;

// 全局代理URL
lazy_static! {
    static ref PROXY_URL: Mutex<Option<String>> = Mutex::new(None);
}

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
        Err(e) => {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_download_python() {
        let result = download_python("3.12.8", "20241219", "x86_64-pc-windows-msvc", "C:\\Users\\sunxf\\AppData\\Roaming\\com.ssui.app").await;
        assert!(result.is_ok());
    }
}

