use tauri_plugin_http::reqwest;

#[tauri::command(rename_all = "snake_case")]
pub async fn download_python(version: &str, release_date: &str, architecture: &str, path: &str) -> Result<String, String> {
    let url = format!(
        "https://github.com/astral-sh/python-build-standalone/releases/download/{release_date}/cpython-{version}+{release_date}-{architecture}-install_only_stripped.tar.gz"
    );
    println!("下载URL: {}", url);
    let res = reqwest::get(url).await;

    if res.is_err() {
        return Err("下载失败".to_string());
    }

    // 检查响应状态码
    if !res.as_ref().unwrap().status().is_success() {
        return Err(format!("下载失败,状态码: {}", res.unwrap().status()));
    }

    // 检查Content-Type头,确保是二进制文件
    let content_type = res.as_ref()
        .unwrap()
        .headers()
        .get("content-type")
        .and_then(|h| h.to_str().ok())
        .unwrap_or("");

    if !content_type.contains("application/octet-stream") && 
       !content_type.contains("application/x-gzip") {
        return Err(format!("下载内容不是预期的文件类型: {}", content_type));
    }

    let res = res.unwrap();
    let bytes = res.bytes().await.map_err(|e| e.to_string())?;

    // 直接从内存中的bytes创建读取器
    let cursor = std::io::Cursor::new(bytes);
    let tar = flate2::read::GzDecoder::new(cursor);
    
    // 解压tar
    println!("解压到: {}", path);
    let mut archive = tar::Archive::new(tar);
    archive.unpack(path).map_err(|e| e.to_string())?;

    return Ok("success".to_string());
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

