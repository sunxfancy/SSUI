from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from ssui import PoseFrame, PoseLandmark, SkeletonAnimation


@dataclass(frozen=True)
class JointSpec:
    name: str
    parent: str | None
    source: str | tuple[str, str]
    canonical_axis: tuple[float, float, float]
    primary_child: str | None = None


JOINTS = (
    JointSpec("Hips", None, ("left_hip", "right_hip"), (0, 1, 0), "Spine"),
    JointSpec("Spine", "Hips", ("left_hip", "right_hip"), (0, 1, 0), "Chest"),
    JointSpec("Chest", "Spine", ("left_shoulder", "right_shoulder"), (0, 1, 0), "Neck"),
    JointSpec("Neck", "Chest", ("left_shoulder", "right_shoulder"), (0, 1, 0), "Head"),
    JointSpec("Head", "Neck", "nose", (0, 1, 0)),
    JointSpec("LeftShoulder", "Chest", "left_shoulder", (-1, 0, 0), "LeftArm"),
    JointSpec("LeftArm", "LeftShoulder", "left_elbow", (-1, 0, 0), "LeftForeArm"),
    JointSpec("LeftForeArm", "LeftArm", "left_wrist", (-1, 0, 0), "LeftHand"),
    JointSpec("LeftHand", "LeftForeArm", "left_index", (-1, 0, 0)),
    JointSpec("RightShoulder", "Chest", "right_shoulder", (1, 0, 0), "RightArm"),
    JointSpec("RightArm", "RightShoulder", "right_elbow", (1, 0, 0), "RightForeArm"),
    JointSpec("RightForeArm", "RightArm", "right_wrist", (1, 0, 0), "RightHand"),
    JointSpec("RightHand", "RightForeArm", "right_index", (1, 0, 0)),
    JointSpec("LeftUpLeg", "Hips", "left_hip", (-1, 0, 0), "LeftLeg"),
    JointSpec("LeftLeg", "LeftUpLeg", "left_knee", (0, -1, 0), "LeftFoot"),
    JointSpec("LeftFoot", "LeftLeg", "left_ankle", (0, -1, 0), "LeftToe"),
    JointSpec("LeftToe", "LeftFoot", "left_foot_index", (0, 0, -1)),
    JointSpec("RightUpLeg", "Hips", "right_hip", (1, 0, 0), "RightLeg"),
    JointSpec("RightLeg", "RightUpLeg", "right_knee", (0, -1, 0), "RightFoot"),
    JointSpec("RightFoot", "RightLeg", "right_ankle", (0, -1, 0), "RightToe"),
    JointSpec("RightToe", "RightFoot", "right_foot_index", (0, 0, -1)),
)
JOINT_BY_NAME = {joint.name: joint for joint in JOINTS}
CHILDREN = {joint.name: [child.name for child in JOINTS if child.parent == joint.name] for joint in JOINTS}


@dataclass
class BVHExport:
    content: str
    report: dict


def _point_map(frame: PoseFrame) -> dict[str, PoseLandmark]:
    return {point.name: point for point in frame.landmarks}


def _raw_point(point: PoseLandmark, animation: SkeletonAnimation) -> np.ndarray:
    if point.world_x is not None and point.world_y is not None and point.world_z is not None:
        # BVH convention: X right, Y up, Z forward. Blender converts this to Z-up.
        return np.array((point.world_x, point.world_y, point.world_z), dtype=float)
    aspect = animation.width / animation.height if animation.height else 1.0
    return np.array(((point.x - 0.5) * aspect, 0.5 - point.y, point.z), dtype=float)


def joint_positions(frame: PoseFrame, animation: SkeletonAnimation) -> dict[str, np.ndarray]:
    points = _point_map(frame)

    def source(value: str | tuple[str, str]) -> np.ndarray | None:
        names = (value,) if isinstance(value, str) else value
        found = [_raw_point(points[name], animation) for name in names if name in points]
        return np.mean(found, axis=0) if len(found) == len(names) else None

    positions = {joint.name: source(joint.source) for joint in JOINTS}
    hips = positions["Hips"]
    chest = positions["Chest"]
    if hips is not None and chest is not None:
        positions["Spine"] = hips * 0.5 + chest * 0.5
        shoulder_width = np.linalg.norm(
            _raw_point(points["right_shoulder"], animation) - _raw_point(points["left_shoulder"], animation)
        ) if "left_shoulder" in points and "right_shoulder" in points else 0.2
        positions["Neck"] = chest + _safe_unit(chest - hips) * shoulder_width * 0.18
    return {name: value for name, value in positions.items() if value is not None}


def _safe_unit(vector: np.ndarray, fallback=(0.0, 1.0, 0.0)) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    return vector / length if length > 1e-8 else np.asarray(fallback, dtype=float)


def _rotation_between(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    a, b = _safe_unit(source), _safe_unit(target)
    cross = np.cross(a, b)
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if dot < -0.999999:
        helper = np.array((1.0, 0.0, 0.0)) if abs(a[0]) < 0.9 else np.array((0.0, 0.0, 1.0))
        axis = _safe_unit(np.cross(a, helper))
        return Rotation.from_rotvec(axis * math.pi).as_matrix()
    skew = np.array(((0, -cross[2], cross[1]), (cross[2], 0, -cross[0]), (-cross[1], cross[0], 0)))
    return np.eye(3) + skew + skew @ skew / max(1e-8, 1 + dot)


def _body_frame(up: np.ndarray, right: np.ndarray) -> np.ndarray:
    y = _safe_unit(up)
    x = _safe_unit(right - y * np.dot(right, y), (1, 0, 0))
    z = _safe_unit(np.cross(x, y), (0, 0, 1))
    x = _safe_unit(np.cross(y, z), (1, 0, 0))
    return np.column_stack((x, y, z))


def _valid_frames(animation: SkeletonAnimation):
    return [(frame, joint_positions(frame, animation)) for frame in animation.frames if frame.landmarks]


def _offsets(frames: list[tuple[PoseFrame, dict[str, np.ndarray]]]) -> dict[str, np.ndarray]:
    result = {"Hips": np.zeros(3)}
    for joint in JOINTS[1:]:
        lengths = []
        for _, positions in frames:
            if joint.name in positions and joint.parent in positions:
                lengths.append(float(np.linalg.norm(positions[joint.name] - positions[joint.parent])))
        length = float(np.median(lengths)) if lengths else 0.1
        result[joint.name] = _safe_unit(np.asarray(joint.canonical_axis, dtype=float)) * max(length, 1e-4)
    return result


def _world_rotations(positions: dict[str, np.ndarray], offsets: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    rotations: dict[str, np.ndarray] = {}
    hips, chest = positions.get("Hips"), positions.get("Chest")
    left_hip, right_hip = positions.get("LeftUpLeg"), positions.get("RightUpLeg")
    if hips is not None and chest is not None and left_hip is not None and right_hip is not None:
        rotations["Hips"] = _body_frame(chest - hips, right_hip - left_hip)
    else:
        rotations["Hips"] = np.eye(3)
    for joint in JOINTS[1:]:
        if joint.name == "Chest" and all(name in positions for name in ("Spine", "Neck", "LeftShoulder", "RightShoulder")):
            rotations[joint.name] = _body_frame(
                positions["Neck"] - positions["Spine"], positions["RightShoulder"] - positions["LeftShoulder"]
            )
        elif joint.primary_child and joint.name in positions and joint.primary_child in positions:
            rotations[joint.name] = _rotation_between(
                offsets[joint.primary_child], positions[joint.primary_child] - positions[joint.name]
            )
        else:
            parent_rotation = rotations.get(joint.parent, np.eye(3))
            rotations[joint.name] = parent_rotation
    return rotations


def _screen_root(frame: PoseFrame, animation: SkeletonAnimation, scale: float) -> np.ndarray:
    points = _point_map(frame)
    if "left_hip" not in points or "right_hip" not in points:
        return np.zeros(3)
    hip_x = (points["left_hip"].x + points["right_hip"].x) * 0.5
    hip_y = (points["left_hip"].y + points["right_hip"].y) * 0.5
    aspect = animation.width / animation.height if animation.height else 1.0
    return np.array(((hip_x - 0.5) * aspect * scale, (0.5 - hip_y) * scale, 0.0))


def _motion(animation: SkeletonAnimation, frames, offsets):
    rows = []
    local_matrices = []
    root_scale = sum(np.linalg.norm(offset) for name, offset in offsets.items() if "Leg" in name) or 1.0
    base_screen = _screen_root(frames[0][0], animation, root_scale)
    for frame, positions in frames:
        world = _world_rotations(positions, offsets)
        locals_for_frame = {}
        root_position = positions.get("Hips", np.zeros(3)) + _screen_root(frame, animation, root_scale) - base_screen
        values = list(root_position)
        for joint in JOINTS:
            parent_world = world.get(joint.parent, np.eye(3))
            local = parent_world.T @ world.get(joint.name, parent_world)
            locals_for_frame[joint.name] = local
            values.extend(Rotation.from_matrix(local).as_euler("XYZ", degrees=False))
        rows.append(np.asarray(values, dtype=float))
        local_matrices.append(locals_for_frame)
    matrix = np.vstack(rows)
    matrix[:, 3:] = np.unwrap(matrix[:, 3:], axis=0)
    matrix[:, 3:] = np.degrees(matrix[:, 3:])
    return matrix, local_matrices


def _hierarchy(name: str, offsets: dict[str, np.ndarray], indent=0) -> list[str]:
    joint = JOINT_BY_NAME[name]
    prefix = "  " * indent
    lines = [f"{prefix}{'ROOT' if joint.parent is None else 'JOINT'} {name}", f"{prefix}{{"]
    offset = offsets[name]
    lines.append(f"{prefix}  OFFSET {offset[0]:.8f} {offset[1]:.8f} {offset[2]:.8f}")
    channels = "6 Xposition Yposition Zposition Xrotation Yrotation Zrotation" if joint.parent is None else "3 Xrotation Yrotation Zrotation"
    lines.append(f"{prefix}  CHANNELS {channels}")
    children = CHILDREN[name]
    for child in children:
        lines.extend(_hierarchy(child, offsets, indent + 1))
    if not children:
        axis = _safe_unit(offset) * max(np.linalg.norm(offset) * 0.25, 0.01)
        lines.extend((f"{prefix}  End Site", f"{prefix}  {{", f"{prefix}    OFFSET {axis[0]:.8f} {axis[1]:.8f} {axis[2]:.8f}", f"{prefix}  }}"))
    lines.append(f"{prefix}}}")
    return lines


def _forward_kinematics(root, locals_for_frame, offsets):
    positions = {"Hips": np.asarray(root, dtype=float)}
    world = {}
    for joint in JOINTS:
        parent_world = world.get(joint.parent, np.eye(3))
        world[joint.name] = parent_world @ locals_for_frame[joint.name]
        if joint.parent:
            positions[joint.name] = positions[joint.parent] + parent_world @ offsets[joint.name]
    return positions


def _report(animation, frames, offsets, motion, local_matrices):
    errors: dict[str, list[float]] = {joint.name: [] for joint in JOINTS}
    reconstructed = []
    targets = []
    for index, ((_, target), local) in enumerate(zip(frames, local_matrices)):
        result = _forward_kinematics(motion[index, :3], local, offsets)
        reconstructed.append({name: value.tolist() for name, value in result.items()})
        target_root = target.get("Hips", np.zeros(3))
        aligned_target = {name: value - target_root + motion[index, :3] for name, value in target.items()}
        targets.append({name: value.tolist() for name, value in aligned_target.items()})
        for name in result.keys() & target.keys():
            errors[name].append(float(np.linalg.norm(result[name] - aligned_target[name])))
    samples = [value for values in errors.values() for value in values]
    return {
        "schema": "ssui.motion.retarget-report/v1",
        "frames": len(frames),
        "rmse": math.sqrt(sum(value * value for value in samples) / len(samples)) if samples else 0.0,
        "max_error": max(samples, default=0.0),
        "per_joint_mean": {name: float(np.mean(values)) if values else None for name, values in errors.items()},
        "units": "mediapipe-world-meters-or-normalized-fallback",
        "root_motion": "screen-space-estimate; monocular metric translation unavailable",
        "target": targets,
        "reconstructed": reconstructed,
    }


def to_bvh(animation: SkeletonAnimation) -> BVHExport:
    frames = _valid_frames(animation)
    if not frames:
        raise ValueError("Skeleton animation has no frames with landmarks")
    offsets = _offsets(frames)
    motion, local_matrices = _motion(animation, frames, offsets)
    lines = ["HIERARCHY", *_hierarchy("Hips", offsets), "MOTION", f"Frames: {len(frames)}", f"Frame Time: {1.0 / animation.fps:.9f}"]
    lines.extend(" ".join(f"{value:.7f}" for value in row) for row in motion)
    report = _report(animation, frames, offsets, motion, local_matrices)
    return BVHExport("\n".join(lines) + "\n", report)


def export_bvh(animation: SkeletonAnimation, path: str | Path) -> BVHExport:
    result = to_bvh(animation)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.content, encoding="utf-8")
    output.with_suffix(".retarget.json").write_text(json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
