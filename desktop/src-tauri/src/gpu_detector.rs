use log::{debug, info};

#[tauri::command]
pub fn detect_gpu() -> Result<Vec<GpuInfo>, String> {
    info!("开始检测GPU");
    let mut gpus = Vec::new();

    #[cfg(target_os = "windows")]
    unsafe {
        // use DXGI to check GPU information on Windows

        use windows::Win32::Graphics::Direct3D::*;
        use windows::Win32::Graphics::Direct3D12::*;
        use windows::Win32::Graphics::Dxgi::*;

        if let Ok(factor) = CreateDXGIFactory2::<IDXGIFactory4>(DXGI_CREATE_FACTORY_FLAGS(0)) {
            let mut i = 0;
            loop {
                if let Ok(adapter) = factor.EnumAdapters1(i) {
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

                    // use D3D12 to check UMA or discrete GPU, necessary?
                    let is_uma = {
                        let mut device: Option<ID3D12Device> = None;
                        D3D12CreateDevice(&adapter, D3D_FEATURE_LEVEL_11_0, &mut device).unwrap();
                        let device = device.unwrap();
                        let mut feature = D3D12_FEATURE_DATA_ARCHITECTURE::default();
                        device
                            .CheckFeatureSupport(
                                D3D12_FEATURE_ARCHITECTURE,
                                &raw mut feature as *mut _,
                                size_of::<D3D12_FEATURE_DATA_ARCHITECTURE>() as u32,
                            )
                            .unwrap();
                        feature.UMA.as_bool()
                    };

                    let name = String::from_utf16_lossy(&desc.Description);
                    let vram = if is_uma {
                        desc.SharedSystemMemory / (1024 * 1024)
                    } else {
                        desc.DedicatedVideoMemory / (1024 * 1024)
                    };

                    debug!("GPU类型: {}", gpu_type);

                    gpus.push(GpuInfo {
                        name,
                        gpu_type: gpu_type.to_string(),
                        vram_mb: vram as u64,
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
        for line in output_str.lines() {
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
                    name: name.clone(),
                    gpu_type: "Apple".to_string(),
                    vram_mb: vram,
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

        for line in output_str.lines() {
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
                    name,
                    gpu_type: gpu_type.to_string(),
                    vram_mb: 0, // Linux下获取显存大小需要更复杂的方法
                });
            }
        }
    }

    info!("GPU检测完成，找到 {} 个GPU", gpus.len());
    Ok(gpus)
}

#[derive(serde::Serialize)]
pub struct GpuInfo {
    name: String,
    gpu_type: String,
    vram_mb: u64,
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
                "名称: {}, 类型: {}, 显存: {}MB",
                gpu.name, gpu.gpu_type, gpu.vram_mb
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
            assert!(gpu.vram_mb > 0, "显存大小不应为负数");
        }
    }
}
