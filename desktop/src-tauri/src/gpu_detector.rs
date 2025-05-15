use log::{debug, info};

#[tauri::command]
pub fn detect_gpu() -> Result<Vec<GpuInfo>, String> {
    info!("开始检测GPU");
    let mut gpus = Vec::new();

    #[cfg(target_os = "windows")]
    unsafe {
        // use DXGI to check GPU information on Windows
        use windows::Win32::Graphics::Dxgi::*;

        if let Ok(factor) = CreateDXGIFactory2::<IDXGIFactory4>(DXGI_CREATE_FACTORY_FLAGS(0)) {
            let mut i = 0;
            loop {
                if let Ok(adapter) = factor.EnumAdapters1(i) {
                    let device_index = i;
                    i += 1;

                    let desc = adapter.GetDesc1().unwrap();

                    // skip software adapters
                    if DXGI_ADAPTER_FLAG_SOFTWARE.0 & (desc.Flags as i32) != 0 {
                        continue;
                    }

                    // https://devicehunt.com/all-pci-vendors
                    let gpu_type = match desc.VendorId {
                        0x10DE => "NVIDIA",
                        0x1002 => "AMD", // 0x1022 is also AMD, but there is no gpu devices.
                        0x8086 => "Intel",
                        _ => "Unknown",
                    };

                    let name = String::from_utf16_lossy(&desc.Description);
                    debug!("GPU类型: {}", gpu_type);
                    gpus.push(GpuInfo {
                        device_index,
                        name,
                        gpu_type: gpu_type.to_string(),
                        local_vram: desc.DedicatedVideoMemory as u64,
                        shared_vram: desc.SharedSystemMemory as u64,
                    });
                } else {
                    break;
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        // macOS下使用system_profiler获取GPU信息
        use std::process::Command;

        let output = Command::new("system_profiler")
            .arg("SPDisplaysDataType")
            .output()
            .map_err(|e| e.to_string())?;

        let output_str = String::from_utf8_lossy(&output.stdout);

        // 解析system_profiler输出
        for (index, line) in output_str.lines().enumerate() {
            if line.contains("Chipset Model:") {
                let name = line
                    .split(":")
                    .nth(1)
                    .unwrap_or("Unknown")
                    .trim()
                    .to_string();
                let vram_line = output_str
                    .lines()
                    .find(|l| l.contains("VRAM"))
                    .and_then(|l| l.split(":").nth(1))
                    .unwrap_or(" 0 MB");

                let vram = vram_line
                    .trim()
                    .split(" ")
                    .next()
                    .and_then(|n| n.parse::<u64>().ok())
                    .unwrap_or(0);

                gpus.push(GpuInfo {
                    device_index: index as u32,
                    name: name.clone(),
                    gpu_type: "Apple".to_string(),
                    local_vram: 0,
                    shared_vram: vram * 1024 * 1024, // assume apple is always uma
                });
            }
        }
    }

    #[cfg(target_os = "linux")]
    {
        // Linux下使用lspci命令获取GPU信息
        use std::process::Command;

        let output = Command::new("lspci")
            .arg("-v")
            .output()
            .map_err(|e| e.to_string())?;

        let output_str = String::from_utf8_lossy(&output.stdout);

        for (index, line) in output_str.lines().enumerate() {
            if line.contains("VGA") || line.contains("3D") {
                let name = line
                    .split(":")
                    .nth(2)
                    .unwrap_or("Unknown")
                    .trim()
                    .to_string();

                let gpu_type = if name.to_lowercase().contains("nvidia") {
                    "NVIDIA"
                } else if name.to_lowercase().contains("amd") {
                    "AMD"
                } else {
                    "Unknown"
                };

                gpus.push(GpuInfo {
                    device_index: index as u32,
                    name,
                    gpu_type: gpu_type.to_string(),
                    local_vram: 0, // Linux下获取显存较复杂，暂时设为0
                    shared_vram: 0,
                });
            }
        }
    }

    info!("GPU检测完成，找到 {} 个GPU", gpus.len());
    Ok(gpus)
}

#[derive(serde::Serialize)]
pub struct GpuInfo {
    device_index: u32,
    name: String,
    gpu_type: String,
    local_vram: u64,
    shared_vram: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_gpus() {
        let result = detect_gpu();
        assert!(result.is_ok(), "GPU检测应该成功执行");

        let gpus = result.unwrap();
        println!("检测到的GPU列表:");
        for gpu in &gpus {
            println!(
                "设备序号: {}, 名称: {}, 类型: {}, 独立显存: {}MB, 共享显存: {}MB",
                gpu.device_index,
                gpu.name,
                gpu.gpu_type,
                gpu.local_vram / 1024 / 1024,
                gpu.shared_vram / 1024 / 1024,
            );
        }

        assert!(!gpus.is_empty(), "应该至少检测到一个GPU设备");

        // 验证GPU信息格式是否正确
        for gpu in gpus {
            assert!(!gpu.name.is_empty(), "GPU名称不应为空");
            assert!(
                ["NVIDIA", "AMD", "Intel", "Unknown"].contains(&gpu.gpu_type.as_str()),
                "GPU类型应该是NVIDIA、AMD、Intel或Unknown之一"
            );
            assert!(gpu.local_vram + gpu.shared_vram > 0, "显存大小不应为负数");
        }
    }
}
