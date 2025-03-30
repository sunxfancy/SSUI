use std::collections::HashMap;
use wmi::{COMLibrary, WMIConnection};
use winreg::enums::*;
use winreg::RegKey;

#[tauri::command]
pub fn detect_gpu() -> Result<Vec<GpuInfo>, String> {
    let mut gpus = Vec::new();

    #[cfg(target_os = "windows")]
    {
        // Windows下使用WMI查询GPU信息和注册表获取显存
        let com_con = COMLibrary::new().map_err(|e| e.to_string())?;
        let wmi_con = WMIConnection::new(com_con).map_err(|e| e.to_string())?;
        
        let results: Vec<HashMap<String, wmi::Variant>> = wmi_con
            .raw_query("SELECT Caption, AdapterRAM FROM Win32_VideoController")
            .map_err(|e| e.to_string())?;

        for gpu in results {
            let name = match gpu.get("Caption") {
                Some(wmi::Variant::String(s)) => s.clone(),
                _ => String::from("Unknown"),
            };
            
            let mut vram: u64 = match gpu.get("AdapterRAM") {
                Some(wmi::Variant::UI4(v)) => (*v as u64) / (1024 * 1024),
                _ => 0,
            };

            if vram == 4095 {
                // vram表示溢出，对于独立显卡，尝试从注册表获取显存信息
                let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
                if let Ok(gpu_reg) = hklm.open_subkey("SYSTEM\\ControlSet001\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\0000") {
                    if let Ok(mem_size) = gpu_reg.get_raw_value("HardwareInformation.qwMemorySize") {
                        if let Ok(bytes) = mem_size.bytes.try_into() {
                            // 转换字节数组为u64
                            let qw_memory_size = u64::from_ne_bytes(bytes);
                            vram = qw_memory_size / (1024 * 1024); // 转换为MB
                        }
                    }
                }
            }

            let gpu_type = if name.to_lowercase().contains("nvidia") {
                "NVIDIA"
            } else if name.to_lowercase().contains("amd") {
                "AMD"
            } else if name.to_lowercase().contains("intel") {
                "Intel"
            } else {
                "Unknown"
            };

            gpus.push(GpuInfo {
                name,
                gpu_type: gpu_type.to_string(),
                vram_mb: vram,
            });
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
                let name = line.split(":").nth(1).unwrap_or("Unknown").trim().to_string();
                let vram_line = output_str.lines()
                    .find(|l| l.contains("VRAM"))
                    .and_then(|l| l.split(":").nth(1))
                    .unwrap_or(" 0 MB");
                    
                let vram = vram_line.trim()
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
                let name = line.split(":").nth(2).unwrap_or("Unknown").trim().to_string();
                
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
            println!("名称: {}, 类型: {}, 显存: {}MB", 
                gpu.name, gpu.gpu_type, gpu.vram_mb);
        }
        
        assert!(!gpus.is_empty(), "应该至少检测到一个GPU设备");
        
        // 验证GPU信息格式是否正确
        for gpu in gpus {
            assert!(!gpu.name.is_empty(), "GPU名称不应为空");
            assert!(["NVIDIA", "AMD", "Unknown"].contains(&gpu.gpu_type.as_str()), 
                "GPU类型应该是NVIDIA、AMD或Unknown之一");
            assert!(gpu.vram_mb > 0, "显存大小不应为负数");
        }
    }
}
