use super::*;
use std::time::{Duration, Instant};

fn python() -> String {
    std::env::var("SSUI_TEST_PYTHON").unwrap_or_else(|_| if cfg!(windows) { "python" } else { "python3" }.into())
}

#[tokio::test]
async fn foreground_command_preserves_unicode_arguments_cwd_and_stderr() {
    let dir = tempfile::tempdir().unwrap();
    let cwd = dir.path().join("中文 space & directory");
    std::fs::create_dir(&cwd).unwrap();
    let script = "import os,sys; print(os.getcwd()); print(sys.argv[1])";
    let output = run_python(&python(), cwd.to_str().unwrap(), vec!["-c", script, "value & 中文"]).await.unwrap();
    assert!(output.contains("中文 space & directory"));
    assert!(output.contains("value & 中文"));
    let error = run_python(&python(), cwd.to_str().unwrap(), vec!["-c", "import sys; sys.stderr.write('fixture failure'); sys.exit(7)"]).await.unwrap_err();
    assert!(error.contains("fixture failure"));
}

#[tokio::test]
async fn missing_executable_returns_error_instead_of_panicking() {
    let dir = tempfile::tempdir().unwrap();
    assert!(run_python(dir.path().join("absent").to_str().unwrap(), dir.path().to_str().unwrap(), vec![]).await.is_err());
}

#[test]
fn production_start_status_restart_and_stop_commands() {
    // One test owns global command state; the manager tests use local instances.
    GLOBAL_PROCESS_STATE.process_manager().kill_all_processes();
    let dir = tempfile::tempdir().unwrap();
    for name in ["server", "ss_executor"] {
        std::fs::write(dir.path().join(format!("{name}.py")), "import time\ntime.sleep(60)\n").unwrap();
    }
    let cwd = dir.path().to_str().unwrap();
    let path = python();
    let first = start_server(&path, cwd).unwrap();
    let duplicate = start_server(&path, cwd).unwrap();
    assert_eq!(first.pid, duplicate.pid);
    assert!(get_server_status().unwrap().is_running);
    let executor = start_executor(&path, cwd).unwrap();
    assert_ne!(executor.pid, first.pid);
    let replacement = restart_server(&path, cwd).unwrap();
    assert_ne!(replacement.pid, first.pid);
    assert!(stop_server());
    assert!(!get_server_status().unwrap().is_running);
    assert_eq!(get_server_status().unwrap().pid, None);
    assert!(get_executor_status().unwrap().is_running);
    assert!(stop_executor());
    assert!(!stop_executor());
    assert!(!get_executor_status().unwrap().is_running);
    assert!(start_server("ssui-executable-does-not-exist", cwd).is_err());
    assert!(!get_server_status().unwrap().is_running);
    // Regression: a single argument used to index args[1] and panic.
    let background = run_python_background(&path, cwd, vec!["--version"]).unwrap();
    assert!(!background.pid.is_empty());
    let deadline = Instant::now() + Duration::from_secs(5);
    let mut printed = false;
    while Instant::now() < deadline {
        printed = std::fs::read_dir(dir.path()).unwrap().flatten().any(|entry| {
            std::fs::read_to_string(entry.path()).unwrap_or_default().contains("Python ")
        });
        if printed { break; }
        std::thread::sleep(Duration::from_millis(10));
    }
    GLOBAL_PROCESS_STATE.processes_guard().kill_all_processes();
    assert!(printed, "single-argument background command must execute and write stdout");
}
