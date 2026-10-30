"""Opt-in real model acceptance through the running SSUI HTTP/scheduler/executor stack."""
import argparse
import hashlib
import io
import json
import platform
import sysconfig
import time
from pathlib import Path

import requests
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]


def descriptor(function, **params):
    return {"function": function, "params": params}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://localhost:7422")
    parser.add_argument("--check", choices=["sd1", "qwen", "pose"], action="append", required=True)
    parser.add_argument("--sd1-model")
    parser.add_argument("--qwen-model")
    parser.add_argument("--pose-video")
    parser.add_argument("--pose-model")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if platform.system() != "Windows" or sysconfig.get_platform() != "win-arm64":
        parser.error("Run this acceptance script with native Windows ARM64 Python")

    def api(method, route, **kwargs):
        response = requests.request(method, args.server.rstrip("/") + route, timeout=1800, **kwargs)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])
        return result

    def file_bytes(path):
        response = requests.get(args.server.rstrip("/") + "/file", params={"path": path}, timeout=60)
        response.raise_for_status()
        return response.content

    def run(script, function, params, details):
        query = {"script_path": str(ROOT / script), "callable": function}
        functions = api("GET", "/api/script", params={"script_path": query["script_path"]})["functions"]
        if function not in functions:
            raise RuntimeError(f"Workflow discovery failed: {functions}")
        api("POST", "/api/prepare", params=query)
        started = time.monotonic()
        result = api("POST", "/api/execute", params=query, json={"params": params, "details": details})
        return {"seconds": round(time.monotonic() - started, 3), "result": result}

    def required(name):
        value = getattr(args, name)
        if not value or not Path(value).exists():
            parser.error(f"--{name.replace('_', '-')} must point to an existing model/input")
        return str(Path(value).resolve())

    report = {
        "platform": platform.platform(), "python_platform": sysconfig.get_platform(),
        "device": api("GET", "/api/device"), "torch": api("GET", "/api/version"),
        "lock_sha256": hashlib.sha256((ROOT / "dependencies/windows-arm64-cpu.lock").read_bytes()).hexdigest(),
        "checks": {},
    }
    if report["device"] != "cpu":
        raise RuntimeError(f"Expected CPU service, got {report['device']}")
    for check in args.check:
        if check == "sd1":
            entry = run("examples/basic/workflow-sd1.py", "txt2img", {
                "model": descriptor("ssui_image.SD1.SD1Model.load", path=required("sd1_model")),
                "positive": descriptor("ssui.base.Prompt.create", text="a red fox sitting in a green forest, photograph"),
                "negative": descriptor("ssui.base.Prompt.create", text="blurry"),
            }, {"Create Empty Latent": {"width": 512, "height": 512}, "Denoise": {"steps": 4, "seed": 42}})
            image = Image.open(io.BytesIO(file_bytes(entry["result"][0]["path"]))).convert("RGB")
            if image.size != (512, 512) or max(ImageStat.Stat(image).stddev) < 1:
                raise RuntimeError("SD1 produced an invalid or constant image")
            entry["image_size"] = list(image.size)
        elif check == "qwen":
            entry = run("examples/basic/workflow-chat.py", "chat", {
                "model": descriptor("ssui_llm.Qwen.QwenModel.load", model_path=required("qwen_model")),
                "prompt": "Reply with one short sentence: what is the capital of France?",
            }, {"Chat": {"temperature": 0, "max_length": 128, "top_p": 1}})
            text, history = entry["result"]
            if not text.strip() or history[-1][1] != text:
                raise RuntimeError("Qwen returned empty text or inconsistent history")
        else:
            entry = run("examples/advance/workflow-pose.py", "video_to_skeleton", {
                "video": descriptor("ssui.base.Video", path=required("pose_video")),
            }, {"Pose Recognition": {"model_path": required("pose_model"), "sample_fps": 5}})
            video, animation = entry["result"]
            if animation["frames"] < 1 or not file_bytes(video["path"]) or not file_bytes(animation["bvh_path"]):
                raise RuntimeError("Pose workflow did not export video and BVH")
            entry["skeleton_sha256"] = hashlib.sha256(file_bytes(animation["path"])).hexdigest()
        entry["status"] = "passed"
        report["checks"][check] = entry
        print(f"{check}: passed", flush=True)

    # Reports are portable; actual output artifacts remain in the example project.
    serialized = json.dumps(report, ensure_ascii=False, indent=2).replace(str(ROOT).replace("\\", "\\\\"), "<workspace>")
    Path(args.output).write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
