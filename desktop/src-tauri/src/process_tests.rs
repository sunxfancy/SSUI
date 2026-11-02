use super::*;
use std::io::Write;
use std::net::{TcpListener, TcpStream};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

fn eventually(mut check: impl FnMut() -> bool) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while !check() {
        assert!(Instant::now() < deadline, "process condition timed out");
        std::thread::sleep(Duration::from_millis(10));
    }
}

// Spawn the Rust test executable as a lightweight, cross-platform child.
#[test]
fn child_helper() {
    let Some(file) = std::env::var_os("SSUI_PROCESS_TEST_READY") else { return };
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut output = std::fs::File::create(file).unwrap();
    write!(output, "{}", listener.local_addr().unwrap().port()).unwrap();
    output.sync_all().unwrap();
    loop { std::thread::sleep(Duration::from_secs(1)); }
}

fn child(dir: &std::path::Path, name: &str) -> (Child, u16) {
    let ready = dir.join(name);
    let mut child = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "process::tests::child_helper", "--nocapture"])
        .env("SSUI_PROCESS_TEST_READY", &ready)
        .stdout(Stdio::null()).stderr(Stdio::null()).spawn().unwrap();
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Ok(port) = std::fs::read_to_string(&ready).unwrap_or_default().parse::<u16>() {
            return (child, port);
        }
        if Instant::now() >= deadline {
            let _ = child.kill(); let _ = child.wait();
            panic!("test child failed to become ready");
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[test]
fn stop_reaps_child_and_releases_listener() {
    let dir = tempfile::tempdir().unwrap();
    let (child, port) = child(dir.path(), "ready");
    let pid = child.id().to_string();
    let mut manager = ProcessManager::new();
    manager.add_process("server", child).unwrap();
    assert!(manager.is_process_running("server"));
    assert_eq!(manager.get_process_pid("server"), Some(pid));
    assert!(manager.kill_process("server"));
    assert!(!manager.is_process_running("server"));
    assert_eq!(manager.get_process_pid("server"), None);
    assert!(!manager.kill_process("server"));
    eventually(|| TcpStream::connect(("127.0.0.1", port)).is_err());
}

#[test]
fn replacement_cannot_orphan_old_process() {
    let dir = tempfile::tempdir().unwrap();
    let (old, old_port) = child(dir.path(), "old");
    let (new, new_port) = child(dir.path(), "new");
    let new_pid = new.id().to_string();
    let mut manager = ProcessManager::new();
    manager.add_process("server", old).unwrap();
    manager.add_process("server", new).unwrap();
    eventually(|| TcpStream::connect(("127.0.0.1", old_port)).is_err());
    assert_eq!(manager.get_process_pid("server"), Some(new_pid));
    drop(manager);
    eventually(|| TcpStream::connect(("127.0.0.1", new_port)).is_err());
}

#[test]
fn cleanup_stops_server_executor_and_background_children() {
    let dir = tempfile::tempdir().unwrap();
    let mut manager = ProcessManager::new();
    let mut ports = vec![];
    for kind in ["server", "executor"] {
        let (child, port) = child(dir.path(), kind);
        manager.add_process(kind, child).unwrap(); ports.push(port);
    }
    manager.kill_all_processes();
    manager.kill_all_processes();
    for port in ports { eventually(|| TcpStream::connect(("127.0.0.1", port)).is_err()); }
    let (background, port) = child(dir.path(), "background");
    let mut guard = BackgroundProcessesGuard::new();
    guard.add_process(background); drop(guard);
    eventually(|| TcpStream::connect(("127.0.0.1", port)).is_err());
}

#[test]
fn natural_exit_is_removed_from_status() {
    let child = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", "process::tests::child_helper"])
        .env_remove("SSUI_PROCESS_TEST_READY").stdout(Stdio::null()).spawn().unwrap();
    let mut manager = ProcessManager::new();
    manager.add_process("executor", child).unwrap();
    eventually(|| !manager.is_process_running("executor"));
    assert_eq!(manager.get_process_pid("executor"), None);
}
