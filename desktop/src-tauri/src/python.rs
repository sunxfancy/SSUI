use std::process::Command;

#[tauri::command]
pub async fn run_python(path: &str, cwd: &str, args: Vec<&str>) -> Result<String, String> {
    let output = Command::new(path)
        .args(args)
        .current_dir(cwd)
        .output()
        .expect("failed to execute process");

    let stdout = String::from_utf8(output.stdout).expect("failed to convert stdout to string");
    let stderr = String::from_utf8(output.stderr).expect("failed to convert stderr to string");
    if output.status.success() {
        Ok(stdout)
    } else {
        Err(stderr)
    }
}

#[tauri::command]
pub async fn get_dev_root() -> Result<String, String>  {
    let current_dir: std::path::PathBuf = std::env::current_dir().map_err(|e| e.to_string())?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    let current_dir = current_dir.parent().ok_or("无法获取上级目录")?;
    Ok(current_dir.to_string_lossy().into_owned())
}