use super::*;
use std::io::{BufRead, BufReader, Read};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

struct LocalServer {
    url: String,
    stop: Arc<AtomicBool>,
    thread: Option<std::thread::JoinHandle<()>>,
}
impl LocalServer {
    fn new(bytes: Vec<u8>, fail: bool) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        listener.set_nonblocking(true).unwrap();
        let stop = Arc::new(AtomicBool::new(false)); let signal = stop.clone();
        let thread = std::thread::spawn(move || {
            while !signal.load(Ordering::SeqCst) {
                if let Ok((mut stream, _)) = listener.accept() {
                    // Windows accepts inherit the listening socket's nonblocking mode.
                    // Read complete headers before replying, even when packets arrive apart.
                    stream.set_nonblocking(false).unwrap();
                    stream.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
                    let mut request = BufReader::new(stream.try_clone().unwrap());
                    let mut range = None;
                    loop {
                        let mut line = String::new();
                        if request.read_line(&mut line).unwrap_or(0) == 0 || line == "\r\n" { break; }
                        if let Some(value) = line.to_ascii_lowercase().strip_prefix("range: bytes=") {
                            let (start, end) = value.trim().split_once('-').unwrap();
                            range = Some((start.parse::<usize>().unwrap(), end.parse::<usize>().unwrap()));
                        }
                    }
                    let (status, body) = if fail { ("503 Unavailable", &b"failure"[..]) }
                        else if let Some((start, end)) = range { ("206 Partial Content", &bytes[start..=end]) }
                        else { ("200 OK", &bytes[..]) };
                    let header = format!("HTTP/1.1 {status}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", body.len());
                    let _ = stream.write_all(header.as_bytes()); let _ = stream.write_all(body);
                } else { std::thread::sleep(Duration::from_millis(1)); }
            }
        });
        Self { url: format!("http://{address}/fixture"), stop, thread: Some(thread) }
    }
}
impl Drop for LocalServer {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        let _ = TcpStream::connect(self.url.trim_start_matches("http://").trim_end_matches("/fixture"));
        if let Some(thread) = self.thread.take() { thread.join().unwrap(); }
    }
}

#[test]
fn local_fixture_waits_for_fragmented_request_headers() {
    let server = LocalServer::new(b"abcdef".to_vec(), false);
    let address = server.url.trim_start_matches("http://").trim_end_matches("/fixture");
    let mut client = TcpStream::connect(address).unwrap();
    client.write_all(b"GET /fixture HTTP/1.1\r\nHost: localhost\r\nRa").unwrap();
    // A Windows receive timeout leaves the connection unusable; peek without
    // consuming data or timing out a blocking receive before completing headers.
    client.set_nonblocking(true).unwrap();
    let deadline = Instant::now() + Duration::from_millis(100);
    let mut byte = [0];
    while Instant::now() < deadline {
        let error = client.peek(&mut byte).expect_err("must not reply before headers are complete");
        assert_eq!(error.kind(), std::io::ErrorKind::WouldBlock);
        std::thread::sleep(Duration::from_millis(1));
    }
    client.set_nonblocking(false).unwrap();
    client.write_all(b"nge: bytes=1-2\r\n\r\n").unwrap();
    client.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
    let mut response = BufReader::new(client);
    let mut headers = String::new();
    loop {
        let mut line = String::new();
        assert_ne!(response.read_line(&mut line).unwrap(), 0, "response headers must be complete");
        headers.push_str(&line);
        if line == "\r\n" { break; }
    }
    assert!(headers.starts_with("HTTP/1.1 206 Partial Content\r\n"));
    assert!(headers.contains("\r\nContent-Length: 2\r\n"));
    let mut body = [0; 2];
    response.read_exact(&mut body).unwrap();
    assert_eq!(&body, b"bc");
}

#[tokio::test]
async fn concurrent_local_download_is_byte_exact_and_reports_all_blocks() {
    let bytes: Vec<u8> = (0..8193).map(|index| (index % 251) as u8).collect();
    let server = LocalServer::new(bytes.clone(), false);
    let dir = tempfile::tempdir().unwrap();
    let output = dir.path().join("中文 model & data.bin");
    let progress = Arc::new(std::sync::Mutex::new(vec![])); let recorded = progress.clone();
    let downloader = ChunkedDownloader::new(&server.url, output.to_str().unwrap(), 1024)
        .with_max_concurrent(4).with_progress_callback(move |done, total| recorded.lock().unwrap().push((done, total)));
    tokio::time::timeout(Duration::from_secs(10), downloader.download()).await.unwrap().unwrap();
    assert_eq!(std::fs::read(&output).unwrap(), bytes);
    assert_eq!(progress.lock().unwrap().last(), Some(&(9, 9)));
    assert!(!Path::new(&downloader.progress_file).exists());
    for index in 0..9 { assert!(!Path::new(&format!("{}.part{index}", output.display())).exists()); }
}

#[tokio::test]
async fn partial_cached_chunk_is_redownloaded_and_http_failure_never_completes() {
    let bytes = b"local fixture content".to_vec();
    let server = LocalServer::new(bytes.clone(), false);
    let dir = tempfile::tempdir().unwrap();
    let output = dir.path().join("output.bin");
    std::fs::write(format!("{}.part0", output.display()), b"broken").unwrap();
    let downloader = ChunkedDownloader::new(&server.url, output.to_str().unwrap(), 1024);
    downloader.download().await.unwrap();
    assert_eq!(std::fs::read(&output).unwrap(), bytes);
    let failed = LocalServer::new(vec![], true);
    let missing = dir.path().join("never-completed.bin");
    assert!(ChunkedDownloader::new(&failed.url, missing.to_str().unwrap(), 1024).download().await.is_err());
    assert!(!missing.exists());
}

#[tokio::test]
async fn invalid_download_settings_return_errors_without_hanging() {
    let downloader = ChunkedDownloader::new("http://127.0.0.1:1", "unused", 0);
    assert!(downloader.download().await.is_err());
    assert!(ChunkedDownloader::new("http://127.0.0.1:1", "unused", 1).with_max_concurrent(0).download().await.is_err());
}

#[tokio::test]
async fn unpack_round_trips_unicode_files_and_rejects_corruption() {
    let dir = tempfile::tempdir().unwrap();
    let archive_path = dir.path().join("app.tar.gz");
    let file = File::create(&archive_path).unwrap();
    let gzip = flate2::write::GzEncoder::new(file, flate2::Compression::default());
    let mut archive = tar::Builder::new(gzip);
    let data = "中文 fixture".as_bytes();
    let mut header = tar::Header::new_gnu();
    header.set_size(data.len() as u64); header.set_mode(0o644); header.set_cksum();
    archive.append_data(&mut header, "folder/file.txt", data).unwrap();
    archive.into_inner().unwrap().finish().unwrap();
    let target = dir.path().join("中文 app & destination");
    unpack_app(archive_path.to_str().unwrap(), target.to_str().unwrap()).await.unwrap();
    assert_eq!(std::fs::read(target.join("folder/file.txt")).unwrap(), data);
    std::fs::write(&archive_path, b"corrupted archive").unwrap();
    assert!(unpack_app(archive_path.to_str().unwrap(), target.to_str().unwrap()).await.is_err());
    assert!(unpack_app(dir.path().join("absent").to_str().unwrap(), target.to_str().unwrap()).await.is_err());
}
