/// This library is from https://github.com/huggingface/hf_transfer/blob/main/src/lib.rs
/// With python bindings removed
use futures::stream::FuturesUnordered;
use futures::StreamExt;
use rand::{thread_rng, Rng};
use std::collections::HashMap;
use std::fmt::Display;
use std::fs::remove_file;
use std::io::SeekFrom;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;
use tauri_plugin_http::reqwest::{self, Client};
use tauri_plugin_http::reqwest::{
    header::{
        HeaderMap, HeaderName, HeaderValue, ToStrError, AUTHORIZATION, CONTENT_LENGTH,
        CONTENT_RANGE, RANGE,
    },
    Url,
};
use tokio::fs::OpenOptions;
use tokio::io::AsyncWriteExt;
use tokio::io::{AsyncReadExt, AsyncSeekExt};
use tokio::sync::Semaphore;
use tokio::time::sleep;
use tokio_util::codec::{BytesCodec, FramedRead};

const BASE_WAIT_TIME: usize = 300;
const MAX_WAIT_TIME: usize = 10_000;

/// max_files: Number of open file handles, which determines the maximum number of parallel downloads
/// parallel_failures:  Number of maximum failures of different chunks in parallel (cannot exceed max_files)
/// max_retries: Number of maximum attempts per chunk. (Retries are exponentially backed off + jitter)
///
/// The number of threads can be tuned by the environment variable `TOKIO_WORKER_THREADS` as documented in
/// https://docs.rs/tokio/latest/tokio/runtime/struct.Builder.html#method.worker_threads
#[allow(clippy::too_many_arguments)]
pub fn download(
    url: String,
    filename: String,
    max_files: usize,
    chunk_size: usize,
    parallel_failures: usize,
    max_retries: usize,
    headers: Option<HashMap<String, String>>,
    callback: Option<Box<dyn Fn(usize)>>,
) -> Result<(), String> {
    if parallel_failures > max_files {
        return Err("Error parallel_failures cannot be > max_files".to_string());
    }
    if (parallel_failures == 0) != (max_retries == 0) {
        return Err(
            "For retry mechanism you need to set both `parallel_failures` and `max_retries`"
                .to_string(),
        );
    }
    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|err| format!("Error while building runtime: {err}"))?
        .block_on(async {
            download_async(
                url,
                filename.clone(),
                max_files,
                chunk_size,
                parallel_failures,
                max_retries,
                headers,
                callback,
            )
            .await
        })
        .map_err(|err| {
            let path = Path::new(&filename);
            if path.exists() {
                match remove_file(filename) {
                    Ok(_) => err,
                    Err(err) => {
                        format!("Error while removing corrupted file: {err}")
                    }
                }
            } else {
                err
            }
        })
}

/// parts_urls: Dictionary consisting of part numbers as keys and the associated url as values
/// completion_url: The url that should be called when the upload is finished
/// max_files: Number of open file handles, which determines the maximum number of parallel uploads
/// parallel_failures:  Number of maximum failures of different chunks in parallel (cannot exceed max_files)
/// max_retries: Number of maximum attempts per chunk. (Retries are exponentially backed off + jitter)
///
/// The number of threads can be tuned by the environment variable `TOKIO_WORKER_THREADS` as documented in
/// https://docs.rs/tokio/latest/tokio/runtime/struct.Builder.html#method.worker_threads
///
/// See https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html for more information
/// on the multipart upload
#[allow(clippy::too_many_arguments)]
pub fn multipart_upload(
    file_path: String,
    parts_urls: Vec<String>,
    chunk_size: u64,
    max_files: usize,
    parallel_failures: usize,
    max_retries: usize,
    callback: Option<Box<dyn Fn(usize)>>,
) -> Result<Vec<HashMap<String, String>>, String> {
    if parallel_failures > max_files {
        return Err("Error parallel_failures cannot be > max_files".to_string());
    }
    if (parallel_failures == 0) != (max_retries == 0) {
        return Err(
            "For retry mechanism you need to set both `parallel_failures` and `max_retries`"
                .to_string(),
        );
    }

    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|err| format!("Error while building runtime: {err}"))?
        .block_on(async {
            upload_async(
                file_path,
                parts_urls,
                chunk_size,
                max_files,
                parallel_failures,
                max_retries,
                callback,
            )
            .await
        })
}

fn jitter() -> usize {
    thread_rng().gen_range(0..=500)
}

pub fn exponential_backoff(base_wait_time: usize, n: usize, max: usize) -> usize {
    (base_wait_time + n.pow(2) + jitter()).min(max)
}

#[allow(clippy::too_many_arguments)]
pub async fn download_async(
    url: String,
    filename: String,
    max_files: usize,
    chunk_size: usize,
    parallel_failures: usize,
    max_retries: usize,
    input_headers: Option<HashMap<String, String>>,
    callback: Option<Box<dyn Fn(usize)>>,
) -> Result<(), String> {
    let client = Client::builder()
        // https://github.com/hyperium/hyper/issues/2136#issuecomment-589488526
        .http2_keep_alive_timeout(Duration::from_secs(15))
        .build()
        .unwrap();

    let mut headers = HeaderMap::new();
    let mut auth_token = None;
    if let Some(input_headers) = input_headers {
        headers.reserve(input_headers.len());
        for (k, v) in input_headers {
            let name: HeaderName = k
                .try_into()
                .map_err(|err| format!("Invalid header: {err}"))?;
            let value: HeaderValue = AsRef::<str>::as_ref(&v)
                .try_into()
                .map_err(|err| format!("Invalid header value: {err}"))?;
            if name == AUTHORIZATION {
                auth_token = Some(value);
            } else {
                headers.insert(name, value);
            }
        }
    };

    let response = if let Some(token) = auth_token.as_ref() {
        client.get(&url).header(AUTHORIZATION, token)
    } else {
        client.get(&url)
    }
    .headers(headers.clone())
    .header(RANGE, "bytes=0-0")
    .send()
    .await
    .map_err(|err| format!("Error while downloading: {err}"))?
    .error_for_status()
    .map_err(|err| err.to_string())?;

    // Only call the final redirect URL to avoid overloading the Hub with requests and also
    // altering the download count
    let redirected_url = response.url();
    if Url::parse(&url)
        .map_err(|err| format!("failed to parse url: {err}"))?
        .host()
        == redirected_url.host()
    {
        if let Some(token) = auth_token {
            headers.insert(AUTHORIZATION, token);
        }
    }

    let content_range = response
        .headers()
        .get(CONTENT_RANGE)
        .ok_or("No content length")?
        .to_str()
        .map_err(|err| format!("Error while downloading: {err}"))?;

    let size: Vec<&str> = content_range.split('/').collect();
    // Content-Range: bytes 0-0/702517648
    // https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Range
    let length: usize = size
        .last()
        .ok_or("Error while downloading: No size was detected")?
        .parse()
        .map_err(|err| format!("Error while downloading: {err}"))?;

    let mut handles = FuturesUnordered::new();
    let semaphore = Arc::new(Semaphore::new(max_files));
    let parallel_failures_semaphore = Arc::new(Semaphore::new(parallel_failures));

    for start in (0..length).step_by(chunk_size) {
        let url = redirected_url.to_string();
        let filename = filename.clone();
        let client = client.clone();
        let headers = headers.clone();

        let stop = std::cmp::min(start + chunk_size - 1, length);
        let semaphore = semaphore.clone();
        let parallel_failures_semaphore = parallel_failures_semaphore.clone();
        handles.push(tokio::spawn(async move {
            let permit = semaphore
                .acquire_owned()
                .await
                .map_err(|err| format!("Error while downloading: {err}"))?;
            let mut chunk = download_chunk(&client, &url, &filename, start, stop, headers.clone()).await;
            let mut i = 0;
            if parallel_failures > 0 {
                while let Err(dlerr) = chunk {
                    if i >= max_retries {
                        return Err(format!(
                            "Failed after too many retries ({max_retries}): {dlerr}"
                        ));
                    }
                    let parallel_failure_permit = parallel_failures_semaphore.clone().try_acquire_owned().map_err(|err| {
                        format!(
                            "Failed too many failures in parallel ({parallel_failures}): {dlerr} ({err})"
                        )
                    })?;

                    let wait_time = exponential_backoff(BASE_WAIT_TIME, i, MAX_WAIT_TIME);
                    sleep(Duration::from_millis(wait_time as u64)).await;

                    chunk = download_chunk(&client, &url, &filename, start, stop, headers.clone()).await;
                    i += 1;
                    drop(parallel_failure_permit);
                }
            }
            drop(permit);
            chunk.map_err(|e| format!("Downloading error {e}")).and(Ok(stop - start))
        }));
    }

    // Output the chained result
    while let Some(result) = handles.next().await {
        match result {
            Ok(Ok(size)) => {
                if let Some(ref callback) = callback {
                    callback(size);
                }
            }
            Ok(Err(py_err)) => {
                return Err(py_err);
            }
            Err(err) => {
                return Err(format!(
                    "Error while downloading: {err}"
                ));
            }
        }
    }
    Ok(())
}

#[derive(Debug)]
enum Error {
    Io(std::io::Error),
    Request(reqwest::Error),
    ToStrError(ToStrError),
}

impl From<std::io::Error> for Error {
    fn from(value: std::io::Error) -> Self {
        Self::Io(value)
    }
}

impl From<reqwest::Error> for Error {
    fn from(value: reqwest::Error) -> Self {
        Self::Request(value)
    }
}

impl From<ToStrError> for Error {
    fn from(value: ToStrError) -> Self {
        Self::ToStrError(value)
    }
}

impl Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(io) => write!(f, "Io: {io}"),
            Self::Request(req) => write!(f, "Request: {req}"),
            Self::ToStrError(req) => write!(f, "Response non ascii: {req}"),
        }
    }
}

impl std::error::Error for Error {}

async fn download_chunk(
    client: &reqwest::Client,
    url: &str,
    filename: &str,
    start: usize,
    stop: usize,
    headers: HeaderMap,
) -> Result<(), Error> {
    // Process each socket concurrently.
    let range = format!("bytes={start}-{stop}");
    let mut file = OpenOptions::new()
        .write(true)
        .truncate(false)
        .create(true)
        .open(filename)
        .await?;
    file.seek(SeekFrom::Start(start as u64)).await?;
    let response = client
        .get(url)
        .headers(headers)
        .header(RANGE, range)
        .send()
        .await?
        .error_for_status()?;
    let content = response.bytes().await?;
    file.write_all(&content).await?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn upload_async(
    file_path: String,
    parts_urls: Vec<String>,
    chunk_size: u64,
    max_files: usize,
    parallel_failures: usize,
    max_retries: usize,
    callback: Option<Box<dyn Fn(usize)>>,
) -> Result<Vec<HashMap<String, String>>, String> {
    let client = reqwest::Client::new();

    let mut handles = FuturesUnordered::new();
    let semaphore = Arc::new(Semaphore::new(max_files));
    let parallel_failures_semaphore = Arc::new(Semaphore::new(parallel_failures));

    for (part_number, part_url) in parts_urls.iter().enumerate() {
        let url = part_url.to_string();
        let path = file_path.to_owned();
        let client = client.clone();

        let start = (part_number as u64) * chunk_size;
        let semaphore = semaphore.clone();
        let parallel_failures_semaphore = parallel_failures_semaphore.clone();
        handles.push(tokio::spawn(async move {
                    let permit = semaphore
                        .clone()
                        .acquire_owned()
                        .await
                        .map_err(|err| format!("Error acquiring semaphore: {err}"))?;
                    let mut chunk = upload_chunk(&client, &url, &path, start, chunk_size).await;
                    let mut i = 0;
                    if parallel_failures > 0 {
                        while let Err(ul_err) = chunk {
                            if i >= max_retries {
                                return Err(format!(
                                    "Failed after too many retries ({max_retries}): {ul_err}"
                                ));
                            }

                            let parallel_failure_permit = parallel_failures_semaphore.clone().try_acquire_owned().map_err(|err| {
                                format!(
                                    "Failed too many failures in parallel ({parallel_failures}): {ul_err} ({err})"
                                )
                            })?;

                            let wait_time = exponential_backoff(BASE_WAIT_TIME, i, MAX_WAIT_TIME);
                            sleep(Duration::from_millis(wait_time as u64)).await;

                            chunk = upload_chunk(&client, &url, &path, start, chunk_size).await;
                            i += 1;
                            drop(parallel_failure_permit);
                        }
                    }
                    drop(permit);
                    chunk.map_err(|e|{
                        match e {
                            Error::Io(io) => format!("Io error {io}"),
                            Error::Request(req) => format!("Error while sending chunk {req}"),
                            Error::ToStrError(req) => format!("Response header contains non ASCII chars: {req}"),
                        }
                    }).map(|chunk| (part_number, chunk, chunk_size))
                }));
    }

    let mut results: Vec<HashMap<String, String>> = vec![HashMap::default(); parts_urls.len()];

    while let Some(result) = handles.next().await {
        match result {
            Ok(Ok((part_number, headers, size))) => {
                if let Some(ref callback) = callback {
                    callback(size as usize);
                }
                results[part_number] = headers;
            }
            Ok(Err(py_err)) => {
                return Err(py_err);
            }
            Err(err) => {
                return Err(format!(
                    "Error occurred while uploading: {err}"
                ));
            }
        }
    }

    Ok(results)
}

async fn upload_chunk(
    client: &reqwest::Client,
    url: &str,
    path: &str,
    start: u64,
    chunk_size: u64,
) -> Result<HashMap<String, String>, Error> {
    let mut options = OpenOptions::new();
    let mut file = options.read(true).open(path).await?;
    let file_size = file.metadata().await?.len();
    let bytes_transferred = std::cmp::min(file_size - start, chunk_size);

    file.seek(SeekFrom::Start(start)).await?;
    let chunk = file.take(chunk_size);

    let response = client
        .put(url)
        .header(CONTENT_LENGTH, bytes_transferred)
        .body(reqwest::Body::wrap_stream(FramedRead::new(
            chunk,
            BytesCodec::new(),
        )))
        .send()
        .await?;
    let response = response.error_for_status()?;
    let mut headers = HashMap::new();
    for (name, value) in response.headers().into_iter() {
        headers.insert(name.to_string(), value.to_str()?.to_owned());
    }
    Ok(headers)
}
