use serde::Serialize;

#[derive(Serialize)]
pub struct PortOwner {
    pub pid: u32,
    pub name: Option<String>,
}

/// 查找占用指定 TCP 监听端口的进程（跨平台：Windows / macOS / Linux）。
#[tauri::command]
pub fn check_port_owner(port: u16) -> Option<PortOwner> {
    use netstat2::{
        get_sockets_info, AddressFamilyFlags, ProtocolFlags, ProtocolSocketInfo, TcpState,
    };

    let af_flags = AddressFamilyFlags::IPV4 | AddressFamilyFlags::IPV6;
    let proto_flags = ProtocolFlags::TCP;
    let sockets_info = get_sockets_info(af_flags, proto_flags).ok()?;

    let associated_pids = sockets_info.into_iter().find_map(|socket_info| {
        if let ProtocolSocketInfo::Tcp(tcp) = socket_info.protocol_socket_info {
            if tcp.local_port == port && tcp.state == TcpState::Listen {
                return Some(socket_info.associated_pids);
            }
        }
        None
    })?;
    let pid = *associated_pids.first()?;

    Some(PortOwner {
        pid,
        name: process_name(pid),
    })
}

/// 按 PID 终止进程（跨平台）。
#[tauri::command]
pub fn kill_pid(pid: u32) -> bool {
    use sysinfo::{Pid, ProcessesToUpdate, System};

    let mut system = System::new();
    system.refresh_processes(ProcessesToUpdate::All, true);
    match system.process(Pid::from_u32(pid)) {
        Some(process) => process.kill(),
        None => false,
    }
}

fn process_name(pid: u32) -> Option<String> {
    use sysinfo::{Pid, ProcessesToUpdate, System};

    let mut system = System::new();
    system.refresh_processes(ProcessesToUpdate::Some(&[Pid::from_u32(pid)]), true);
    system
        .process(Pid::from_u32(pid))
        .map(|p| p.name().to_string_lossy().into_owned())
}
