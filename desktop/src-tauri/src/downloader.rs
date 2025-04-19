use tauri_plugin_http::reqwest;
use log::{info, error, warn, debug};

#[tauri::command(rename_all = "snake_case")]
pub async fn download_python(version: &str, release_date: &str, architecture: &str, path: &str) -> Result<String, String> {
    let url = format!(
        "https://github.com/astral-sh/python-build-standalone/releases/download/{release_date}/cpython-{version}+{release_date}-{architecture}-install_only_stripped.tar.gz"
    );
    info!("开始下载Python: {}", url);
    debug!("下载参数: version={}, release_date={}, architecture={}, path={}", version, release_date, architecture, path);
    
    let res = reqwest::get(url).await;

    if res.is_err() {
        let err_msg = format!("下载失败: {}", res.err().unwrap());
        error!("{}", err_msg);
        return Err(err_msg);
    }

    // 检查响应状态码
    let status = res.as_ref().unwrap().status();
    if !status.is_success() {
        let err_msg = format!("下载失败,状态码: {}", status);
        error!("{}", err_msg);
        return Err(err_msg);
    }

    // 检查Content-Type头,确保是二进制文件
    let content_type = res.as_ref()
        .unwrap()
        .headers()
        .get("content-type")
        .and_then(|h| h.to_str().ok())
        .unwrap_or("");
    
    debug!("响应Content-Type: {}", content_type);

    if !content_type.contains("application/octet-stream") && 
       !content_type.contains("application/x-gzip") {
        let err_msg = format!("下载内容不是预期的文件类型: {}", content_type);
        error!("{}", err_msg);
        return Err(err_msg);
    }

    let res = res.unwrap();
    let bytes = match res.bytes().await {
        Ok(bytes) => {
            info!("下载完成，文件大小: {} 字节", bytes.len());
            bytes
        },
        Err(e) => {
            let err_msg = format!("读取响应内容失败: {}", e);
            error!("{}", err_msg);
            return Err(err_msg);
        }
    };

    // 直接从内存中的bytes创建读取器
    let cursor = std::io::Cursor::new(bytes);
    let tar = flate2::read::GzDecoder::new(cursor);
    
    // 解压tar
    info!("开始解压到: {}", path);
    let mut archive = tar::Archive::new(tar);
    match archive.unpack(path) {
        Ok(_) => {
            info!("解压完成");
            Ok("success".to_string())
        },
        Err(e) => {
            let err_msg = format!("解压失败: {}", e);
            error!("{}", err_msg);
            Err(err_msg)
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

