"""Convert a person video into SSUI pose data and Blender-ready BVH files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from ssui import Video
from ssui_motion import PoseRecognitionOptions, export_bvh, recognize_pose


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recognize a single-person video and export SSUI Motion artifacts."
    )
    parser.add_argument("--video", required=True, help="Input video file")
    parser.add_argument("--output-dir", required=True, help="Artifact directory")
    parser.add_argument("--sample-fps", type=float, default=24.0)
    parser.add_argument("--smoothing", type=float, default=0.45)
    parser.add_argument("--model-path")
    return parser.parse_args()


def write_overlay(frames, fps: float, path: Path) -> None:
    if not frames:
        raise ValueError("Pose recognition produced no overlay frames")
    width, height = frames[0].size
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create overlay video: {path}")
    try:
        for frame in frames:
            if frame.size != (width, height):
                raise ValueError("Input video changed resolution between frames")
            writer.write(cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR))
    finally:
        writer.release()


def main() -> int:
    args = parse_args()
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Input video not found: {video_path}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    options = PoseRecognitionOptions(
        model_path=args.model_path,
        sample_fps=args.sample_fps,
        smoothing=args.smoothing,
    )
    overlay, animation = recognize_pose(Video(path=str(video_path)), options)
    detected_frames = sum(frame.detected for frame in animation.frames)
    landmark_frames = sum(bool(frame.landmarks) for frame in animation.frames)
    if landmark_frames == 0:
        raise RuntimeError("No person pose was recognized in the input video")

    skeleton_path = output_dir / "skeleton.json"
    overlay_path = output_dir / "pose-overlay.mp4"
    bvh_path = output_dir / "motion.bvh"
    skeleton_path.write_text(
        json.dumps(animation.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_overlay(overlay.frames, animation.fps, overlay_path)
    bvh = export_bvh(animation, bvh_path)

    result = {
        "schema": "ssui.motion.video-pipeline/v1",
        "source": str(video_path),
        "frames": len(animation.frames),
        "detected_frames": detected_frames,
        "landmark_frames": landmark_frames,
        "fps": animation.fps,
        "artifacts": {
            "skeleton": str(skeleton_path),
            "overlay": str(overlay_path),
            "bvh": str(bvh_path),
            "retarget": str(bvh_path.with_suffix(".retarget.json")),
        },
        "retarget_rmse": bvh.report["rmse"],
        "retarget_max_error": bvh.report["max_error"],
    }
    summary_path = output_dir / "pipeline-summary.json"
    summary_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
