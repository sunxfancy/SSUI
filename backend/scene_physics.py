"""Native geometric placement constraints for static scene assets."""

from __future__ import annotations

import numpy as np


RELATIONS = ("floor", "on", "left_of", "right_of", "front_of", "behind",
             "wall_left", "wall_right", "wall_front", "wall_back", "ceiling")


def transformed_bounds(bounds: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """World AABB of a local AABB after rotation, scale and translation."""
    lo, hi = np.asarray(bounds, dtype=float)
    corners = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    points = (transform @ corners.T).T[:, :3]
    return np.stack((points.min(axis=0), points.max(axis=0)))


def resolve_translation(local_bounds: np.ndarray, relation: str,
                        target_bounds: np.ndarray | None = None,
                        clearance: float = 0.05) -> np.ndarray:
    """Place an unrotated/rotated asset relative to target bounds or the floor."""
    if relation not in RELATIONS:
        raise ValueError(f"Unsupported placement relation: {relation}")
    if not np.isfinite(clearance) or clearance < 0 or clearance > 10:
        raise ValueError("clearance must be finite and between 0 and 10")
    lo, hi = local_bounds
    if relation == "floor":
        return np.array([0.0, 0.0, -lo[2]])
    if target_bounds is None:
        raise ValueError(f"{relation} requires a previously placed target")
    target_lo, target_hi = target_bounds
    center = (target_lo + target_hi) / 2
    own_center = (lo + hi) / 2
    position = np.array([center[0] - own_center[0], center[1] - own_center[1],
                         target_lo[2] - lo[2]])
    if relation == "on":
        position[2] = target_hi[2] + clearance - lo[2]
    elif relation == "ceiling":
        position[2] = target_hi[2] - clearance - hi[2]
    elif relation == "wall_left":
        position[0] = target_lo[0] + clearance - lo[0]
        position[2] = center[2] - own_center[2]
    elif relation == "wall_right":
        position[0] = target_hi[0] - clearance - hi[0]
        position[2] = center[2] - own_center[2]
    elif relation == "wall_front":
        position[1] = target_lo[1] + clearance - lo[1]
        position[2] = center[2] - own_center[2]
    elif relation == "wall_back":
        position[1] = target_hi[1] - clearance - hi[1]
        position[2] = center[2] - own_center[2]
    elif relation == "left_of":
        position[0] = target_lo[0] - clearance - hi[0]
    elif relation == "right_of":
        position[0] = target_hi[0] + clearance - lo[0]
    elif relation == "front_of":
        position[1] = target_lo[1] - clearance - hi[1]
    else:
        position[1] = target_hi[1] + clearance - lo[1]
    return position


def penetration_depth(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Positive on all axes only when AABBs overlap volumetrically."""
    return np.minimum(a[1], b[1]) - np.maximum(a[0], b[0])


def separate_static_aabb(candidate: np.ndarray, others: list[np.ndarray],
                         clearance: float = 0.05, *,
                         containment: np.ndarray | None = None,
                         support: np.ndarray | None = None) -> np.ndarray:
    """Remove XY overlap while retaining room and horizontal support bounds."""
    shifted = np.asarray(candidate, dtype=float).copy()
    delta = np.zeros(3)
    def permitted(bounds: np.ndarray) -> bool:
        if containment is not None and (np.any(bounds[0] < containment[0] - 1e-6)
                                         or np.any(bounds[1] > containment[1] + 1e-6)):
            return False
        if support is not None and (np.any(bounds[0, :2] < support[0, :2] - 1e-6)
                                    or np.any(bounds[1, :2] > support[1, :2] + 1e-6)):
            return False
        return True
    if not permitted(shifted):
        raise ValueError("Object exceeds room or support bounds")
    for _ in range(max(1, len(others) * 4)):
        collision = next((other for other in others
                          if np.all(penetration_depth(shifted, other) > 1e-6)), None)
        if collision is None:
            return delta
        options = []
        for axis in (0, 1):
            for amount in (collision[0, axis] - shifted[1, axis] - clearance,
                           collision[1, axis] - shifted[0, axis] + clearance):
                proposed = shifted.copy()
                proposed[:, axis] += amount
                if permitted(proposed):
                    remaining = sum(np.all(penetration_depth(proposed, other) > 1e-6)
                                    for other in others)
                    options.append((remaining, abs(amount), axis, amount, proposed))
        if not options:
            raise ValueError("Unable to resolve collisions within room or support bounds")
        _, _, axis, amount, shifted = min(options, key=lambda option: option[:3])
        delta[axis] += amount
    raise ValueError("Unable to resolve static scene collisions")
