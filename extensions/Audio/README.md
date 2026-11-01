# Audio generation

The Audio extension exposes optional local model adapters. Open
`examples/advance/workflow-audio.py` to use them as SSUI workflow nodes. The
generated `Audio` value appears in the existing audio preview and is copied to
the project's `output/` directory by the executor.

On Windows ROCm, run `yarn audio:setup:shared-rocm` once to install compatible
inference packages into SSUI's configured shared Python. The script builds the
pinned ROCm-compatible vector quantizer and checks that PyTorch and
Transformers remain unchanged. It does not download model weights.

| Task | Adapter | Setup | Model terms |
| --- | --- | --- | --- |
| Instrumental music | MusicGen | `torch`, `transformers`, `soundfile`; `SSUI_MUSICGEN_MODEL` optionally names a local checkpoint | MusicGen weights: CC BY-NC 4.0 |
| Instrumental or vocal music | ACE-Step 1.5 | After shared setup, run `powershell -File extensions/Audio/scripts/setup_ace_step_rocm.ps1 -SharedPackages -DownloadModel`, then set `SSUI_ACE_STEP_ROOT` to `.build/ace-step-1.5` | Check the selected checkpoint terms |
| Short sound or music sample | Stable Audio Open 1.0 | Recent `diffusers`, `soundfile`, `torch`; accept the gated model terms or set `SSUI_STABLE_AUDIO_MODEL` to a local Diffusers directory | Stability AI Community License |
| Full song | YuE2 | Run `powershell -File extensions/Audio/scripts/setup_yue2_rocm.ps1 -DownloadModel`; set `SSUI_YUE2_SOURCE`, `SSUI_YUE2_CHECKPOINT`, and `SSUI_YUE2_VAE` to the three printed paths | Weights: CC BY-NC 4.0 |
| Full song | HeartMuLa | Run `powershell -File extensions/Audio/scripts/setup_heartmula_rocm.ps1 -DownloadModel`; set `SSUI_HEARTMULA_SOURCE` and `SSUI_HEARTMULA_CHECKPOINT` to its printed paths | Official code and released weights: Apache 2.0 |
| Full song | DiffRhythm | After shared setup, run `powershell -File extensions/Audio/scripts/setup_diffrhythm_rocm.ps1 -SharedPackages`; set `SSUI_DIFFRHYTHM_SOURCE` to its printed source path; install eSpeak NG and model weights; supply timestamped LRC lyrics | Code and DiT weights: Apache 2.0; check VAE terms separately |

The `full_song` example uses the current SSUI Python interpreter unless
`SSUI_HEARTMULA_PYTHON` or `SSUI_DIFFRHYTHM_PYTHON` names a separate
environment's Python executable. Model downloads and licenses are not bundled
into the SSUI package.

ACE-Step uses the shared compatible packages and existing ROCm PyTorch wheel.
Its upstream `main` checkpoint download includes a 1.7B
language model even though this adapter currently generates without that LM.
After setup, set `SSUI_ACE_STEP_ROOT` to this worktree's
`.build/ace-step-1.5` directory in the shell that starts SSUI. The adapter
finds the shared vector quantizer and checkpoints beside that root. The setup
scripts retain an isolated fallback for environments without shared Audio setup.

The YuE2 setup likewise leaves the shared environment untouched. On ROCm the
adapter selects upstream `torch-eager` attention and disables MIOpen for its
generation call. An eight-second, 48 kHz stereo smoke succeeded on this R9700;
full song length and quality remain unverified.

HeartMuLa 3B and its codec generated an eight-second, 48 kHz stereo MP3 on
this Windows ROCm machine using shared compatible packages, an isolated
torchtune inference shim, and an eager runner.
The shim explicitly rejects NF4 quantization. DiffRhythm generated a 95-second,
44.1 kHz stereo WAV on the same ROCm machine with shared compatible packages,
a small compatibility overlay pinned to upstream Transformers 4.49.0, local
eSpeak NG, and a source fix for a training-only import. The workflow prefers
`diff-compat-site` beside the source checkout. Long-song quality and
reproducibility across hardware remain unverified.

ACE-Step, YuE2, and HeartMuLa upstream package metadata pins CUDA or different
Torch/Transformers versions, so their source packages remain in local
checkouts. DiffRhythm requires Transformers 4.49.0 while SSUI's ROCm
environment uses 4.57.6; that version and its tokenizer remain isolated.
HeartMuLa's torchtune 0.4.0 remains isolated because its normal import path
pulls in torchao distributed features unavailable in this Windows ROCm build.

On the Windows ROCm R9700 development machine, MusicGen small has been tested
with the existing `torch 2.9.1+rocm7.2.1` environment. Set
`SSUI_MUSICGEN_MODEL` to the downloaded local model directory (for this
worktree, `.build/audio-models/musicgen-small`). Public model downloads can use
`HF_HUB_DISABLE_IMPLICIT_TOKEN=1` if an expired cached login causes 401.
Set `SSUI_AUDIO_TEMP_DIR` to a writable
directory if the system temporary directory is restricted. The R9700 smoke
generated a 32 kHz WAV; this does not validate every model size or duration.

Stable Audio Open is intended for short clips (up to 47 seconds); its model
card notes that vocals are a weak use case. A two-second, 44.1 kHz stereo
sample passed on the R9700 after selecting Euler sampling and disabling MIOpen
for the call. Set `SSUI_STABLE_AUDIO_MODEL` to a local Diffusers snapshot if
working offline. MusicGen is limited to 30 seconds in this adapter.
YuE2's documented starting point is a BF16 NVIDIA GPU with
24 GB VRAM. DiffRhythm's chunked decoding is documented for an 8 GB VRAM
minimum. The short local smokes do not validate long generation quality or
all model checkpoints.

Upstream documentation: [MusicGen](https://huggingface.co/facebook/musicgen-small),
[ACE-Step](https://github.com/ace-step/ACE-Step-1.5),
[Stable Audio Open](https://huggingface.co/stabilityai/stable-audio-open-1.0),
[YuE2](https://github.com/satecay/yue/blob/main/docs/generation.md),
[HeartMuLa](https://github.com/HeartMuLa/heartlib),
[DiffRhythm](https://github.com/ASLP-lab/DiffRhythm).
