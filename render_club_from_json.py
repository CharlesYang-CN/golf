import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh


H36M = {
    "pelvis": 0,
    "r_hip": 1,
    "r_knee": 2,
    "r_ankle": 3,
    "l_hip": 4,
    "l_knee": 5,
    "l_ankle": 6,
    "spine": 7,
    "thorax": 8,
    "neck": 9,
    "head": 10,
    "l_shoulder": 11,
    "l_elbow": 12,
    "l_wrist": 13,
    "r_shoulder": 14,
    "r_elbow": 15,
    "r_wrist": 16,
}

SKELETON_EDGES = [
    ("pelvis", "spine"),
    ("spine", "thorax"),
    ("thorax", "neck"),
    ("neck", "head"),
    ("thorax", "l_shoulder"),
    ("l_shoulder", "l_elbow"),
    ("l_elbow", "l_wrist"),
    ("thorax", "r_shoulder"),
    ("r_shoulder", "r_elbow"),
    ("r_elbow", "r_wrist"),
    ("pelvis", "l_hip"),
    ("l_hip", "l_knee"),
    ("l_knee", "l_ankle"),
    ("pelvis", "r_hip"),
    ("r_hip", "r_knee"),
    ("r_knee", "r_ankle"),
]

CLUB_SCALE = {
    "driver": 2.7,
    "wood": 2.6,
    "iron": 2.4,
    "wedge": 2.2,
}


def _pick(dct, keys):
    if not isinstance(dct, dict):
        return None
    for k in keys:
        if k in dct:
            return dct[k]
    return None


def _to_np(x):
    if x is None:
        return None
    arr = np.asarray(x, dtype=np.float32)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    return arr


def load_mmpose_json(path):
    with open(path, "r", encoding="utf-8") as f:
        blob = json.load(f)

    if isinstance(blob, list):
        frames = blob
    elif isinstance(blob, dict):
        frames = (
            blob.get("instance_info")
            or blob.get("predictions")
            or blob.get("frames")
            or blob.get("data_list")
            or blob.get("results")
            or [blob]
        )
    else:
        raise ValueError("Unsupported JSON format")

    out = []
    for i, frame in enumerate(frames):
        frame_id = i
        inst = frame

        if isinstance(frame, dict):
            frame_id = frame.get("frame_id", i)
            insts = (
                frame.get("instances")
                or frame.get("pred_instances")
                or frame.get("instance_info")
                or frame.get("predictions")
            )
            if isinstance(insts, list) and len(insts) > 0:
                inst = insts[0]
        elif isinstance(frame, list) and len(frame) > 0:
            inst = frame[0]

        kpts3d = _pick(inst, ["keypoints_3d", "keypoints"])
        scores = _pick(inst, ["keypoint_scores", "scores"])

        out.append(
            {
                "frame_id": int(frame_id),
                "keypoints_3d": _to_np(kpts3d),
                "scores": _to_np(scores),
            }
        )
    return out


def unit(v, eps=1e-8):
    n = float(np.linalg.norm(v))
    if n < eps:
        return np.zeros_like(v)
    return v / n


def moving_average(arr, win=5):
    if len(arr) == 0:
        return arr
    win = max(1, int(win))
    if win % 2 == 0:
        win += 1
    if win == 1:
        return arr.copy()
    pad = win // 2
    arr_pad = np.pad(arr, ((pad, pad), (0, 0)), mode="edge")
    out = [arr_pad[i : i + win].mean(axis=0) for i in range(len(arr))]
    return np.stack(out, axis=0)


def smooth_keypoints_over_time(frames, win=7):
    valid_ids = []
    tracks = []
    for i, fr in enumerate(frames):
        k = fr["keypoints_3d"]
        if k is None or k.ndim != 2 or k.shape[0] < 17 or k.shape[1] < 3:
            continue
        valid_ids.append(i)
        tracks.append(k[:17, :3].reshape(-1))

    if not valid_ids:
        return frames

    tracks = np.stack(tracks, axis=0)
    tracks_s = moving_average(tracks, win=win)

    out = []
    for i, fr in enumerate(frames):
        out_fr = dict(fr)
        out.append(out_fr)

    for j, i in enumerate(valid_ids):
        out[i]["keypoints_3d"] = tracks_s[j].reshape(17, 3).astype(np.float32)

    return out


def synthesize_club(frames, handedness="right", club_type="iron", smooth_win=7):
    club_scale = CLUB_SCALE[club_type]
    results = []

    for fr in frames:
        k = fr["keypoints_3d"]
        if k is None or k.ndim != 2 or k.shape[0] < 17 or k.shape[1] < 3:
            results.append(None)
            continue

        l_sho = k[H36M["l_shoulder"]]
        r_sho = k[H36M["r_shoulder"]]
        l_elb = k[H36M["l_elbow"]]
        r_elb = k[H36M["r_elbow"]]
        l_wri = k[H36M["l_wrist"]]
        r_wri = k[H36M["r_wrist"]]

        if handedness == "right":
            lead_elb, lead_wri = l_elb, l_wri
            trail_elb, trail_wri = r_elb, r_wri
        else:
            lead_elb, lead_wri = r_elb, r_wri
            trail_elb, trail_wri = l_elb, l_wri

        grip = 0.5 * (lead_wri + trail_wri)
        dir_lead = unit(lead_wri - lead_elb)
        dir_trail = unit(trail_wri - trail_elb)
        shaft_dir = unit(0.7 * dir_lead + 0.3 * dir_trail)

        shoulder_width = float(np.linalg.norm(l_sho - r_sho))
        club_len = club_scale * shoulder_width

        butt = grip - 0.12 * club_len * shaft_dir
        head = grip + 0.88 * club_len * shaft_dir

        results.append(
            {
                "frame_id": fr["frame_id"],
                "grip": grip,
                "butt": butt,
                "club_head_proxy": head,
            }
        )

    valid_ids = [i for i, x in enumerate(results) if x is not None]
    if valid_ids:
        shaft_dirs = []
        club_lens = []
        for i in valid_ids:
            grip = results[i]["grip"]
            head = results[i]["club_head_proxy"]
            shaft_dirs.append(unit(head - grip))
            club_lens.append(float(np.linalg.norm(head - grip)) / 0.88)

        shaft_dirs = np.stack(shaft_dirs, axis=0)
        club_lens = np.asarray(club_lens, dtype=np.float32)[:, None]
        shaft_dirs_s = moving_average(shaft_dirs, win=smooth_win)
        club_lens_s = moving_average(club_lens, win=smooth_win).reshape(-1)

        for j, i in enumerate(valid_ids):
            grip = results[i]["grip"]  # 保持握把锚点与双腕实时绑定
            shaft_dir = unit(shaft_dirs_s[j])
            club_len = float(club_lens_s[j])
            results[i]["butt"] = grip - 0.12 * club_len * shaft_dir
            results[i]["club_head_proxy"] = grip + 0.88 * club_len * shaft_dir

    return results


def _build_projector(frames, width, height, margin=0.1, azim=0, elev=0, perspective=False):
    """
    Advanced 3D-to-2D projector with rotation and perspective.
    Default (0,0) is Front View (X-Y plane).
    """
    # 1. Collect all points to find center
    pts = []
    for fr in frames:
        if fr["keypoints_3d"] is not None:
            pts.append(fr["keypoints_3d"][:17, :3])
    if not pts:
        raise ValueError("No valid keypoints to project.")
    
    all_pts = np.concatenate(pts, axis=0)
    center = np.mean(all_pts, axis=0)
    
    # 2. Setup Rotation
    # H36M: X-right, Y-forward/depth, Z-up
    # We want a system where we can rotate around the vertical axis (Z)
    a = np.radians(azim)
    e = np.radians(elev)
    
    # Rotation matrices
    Rz = np.array([
        [np.cos(a), -np.sin(a), 0],
        [np.sin(a),  np.cos(a), 0],
        [0,          0,         1]
    ])
    Rx = np.array([
        [1, 0,           0],
        [0, np.cos(e), -np.sin(e)],
        [0, np.sin(e),  np.cos(e)]
    ])
    R = Rx @ Rz

    # 3. Project and find scale
    # Rotate all points to find the bounding box in the view plane
    view_pts = (all_pts - center) @ R.T
    v_min = view_pts.min(axis=0)
    v_max = view_pts.max(axis=0)
    
    span_x = max(1e-6, v_max[0] - v_min[0])
    span_z = max(1e-6, v_max[2] - v_min[2]) # In view space, Z is vertical
    
    avail_w = width * (1 - 2 * margin)
    avail_h = height * (1 - 2 * margin)
    scale = min(avail_w / span_x, avail_h / span_z)

    def project(p):
        # 1. Center and Rotate
        p_v = (np.asarray(p[:3]) - center) @ R.T
        
        # 2. Perspective (optional)
        if perspective:
            # Assume camera is back at some distance
            dist = 5.0 
            focal = 1.0
            z_depth = p_v[1] # Y is depth in rotated space
            factor = focal / (dist + z_depth)
            p_v = p_v * factor * dist

        # 3. Scale and Offset to Screen
        # View X -> Screen X
        # View Z -> Screen Y (inverted)
        x = p_v[0] * scale + width * 0.5
        y = height * 0.5 - p_v[2] * scale
        return int(round(x)), int(round(y))

    return project, center


def draw_skeleton(canvas, k, project, line_width=2):
    # Colors (BGR)
    COLOR_RIGHT = (255, 120, 100) # Blue-ish
    COLOR_LEFT = (100, 120, 255)  # Red-ish
    COLOR_CENTER = (100, 255, 100) # Green-ish
    
    for a, b in SKELETON_EDGES:
        ia, ib = H36M[a], H36M[b]
        pa = project(k[ia])
        pb = project(k[ib])
        
        # Determine color based on joint names
        if "r_" in a or "r_" in b:
            color = COLOR_RIGHT
        elif "l_" in a or "l_" in b:
            color = COLOR_LEFT
        else:
            color = COLOR_CENTER
            
        cv2.line(canvas, pa, pb, color, line_width, lineType=cv2.LINE_AA)

    for i in range(17):
        p = project(k[i])
        cv2.circle(canvas, p, line_width + 1, (240, 240, 240), -1, lineType=cv2.LINE_AA)


def draw_grid(canvas, project, center, size=1.5, steps=10):
    """Draw a ground grid on Z=0 plane."""
    color = (60, 60, 60)
    # X lines
    for i in range(steps + 1):
        x = center[0] - size/2 + i * (size/steps)
        p0 = project([x, center[1] - size/2, 0])
        p1 = project([x, center[1] + size/2, 0])
        cv2.line(canvas, p0, p1, color, 1, lineType=cv2.LINE_AA)
    # Y lines
    for i in range(steps + 1):
        y = center[1] - size/2 + i * (size/steps)
        p0 = project([center[0] - size/2, y, 0])
        p1 = project([center[0] + size/2, y, 0])
        cv2.line(canvas, p0, p1, color, 1, lineType=cv2.LINE_AA)


def apply_view_transform(img, transform):
    if transform == "none":
        return img
    if transform == "rotate-180":
        return cv2.rotate(img, cv2.ROTATE_180)
    if transform == "flip-x":
        return cv2.flip(img, 1)
    if transform == "flip-y":
        return cv2.flip(img, 0)
    raise ValueError(f"Unknown view transform: {transform}")


def render_video(
    frames, club, out_path, fps=30, width=960, height=720, 
    view_transform="rotate-180", azim=0, elev=15, perspective=False,
    bg_video=None
):
    project, center = _build_projector(
        frames, width=width, height=height, 
        azim=azim, elev=elev, perspective=perspective
    )
    
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height)
    )

    cap_bg = None
    if bg_video and Path(bg_video).exists():
        cap_bg = cv2.VideoCapture(str(bg_video))

    for fr, club_fr in zip(frames, club):
        # 1. Prepare Canvas
        if cap_bg:
            ret, canvas = cap_bg.read()
            if not ret:
                canvas = np.full((height, width, 3), 30, dtype=np.uint8)
            else:
                if (canvas.shape[1], canvas.shape[0]) != (width, height):
                    canvas = cv2.resize(canvas, (width, height))
        else:
            # Gradient background for "Professional" look
            canvas = np.zeros((height, width, 3), dtype=np.uint8)
            for i in range(height):
                c = int(15 + 25 * (i / height))
                canvas[i, :] = (c, c, c)
            
            # Draw ground grid
            draw_grid(canvas, project, center)

        k = fr["keypoints_3d"]

        # 2. Draw Human
        if k is not None and k.shape[0] >= 17:
            draw_skeleton(canvas, k, project, line_width=3)

        # 3. Draw Club
        if club_fr is not None:
            butt = project(club_fr["butt"])
            grip = project(club_fr["grip"])
            head = project(club_fr["club_head_proxy"])
            # Shaft
            cv2.line(canvas, butt, head, (0, 220, 255), 4, lineType=cv2.LINE_AA)
            # Grip & Head highlights
            cv2.circle(canvas, grip, 6, (0, 140, 255), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, head, 8, (255, 200, 0), -1, lineType=cv2.LINE_AA)

        # 4. Info Overlays
        fid = fr["frame_id"]
        cv2.putText(canvas, f"FRAME: {fid:03d}", (20, 40), 
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (200, 200, 200), 1, cv2.LINE_AA)
        
        view_info = f"VIEW: AZIM={azim} ELEV={elev}"
        if perspective: view_info += " (PERSP)"
        cv2.putText(canvas, view_info, (20, height - 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1, cv2.LINE_AA)

        if not cap_bg:
            canvas = apply_view_transform(canvas, view_transform)
        
        writer.write(canvas)

    writer.release()
    if cap_bg: cap_bg.release()



def try_read_fps(video_path, fallback=30):
    if not video_path:
        return fallback
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return fallback
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if fps and fps > 1:
        return float(fps)
    return fallback


def _add_sphere(scene, center, radius, color, name):
    mesh = trimesh.creation.icosphere(subdivisions=1, radius=radius)
    mesh.visual.vertex_colors = np.tile(np.array(color, dtype=np.uint8), (len(mesh.vertices), 1))
    mesh.apply_translation(np.asarray(center, dtype=np.float32))
    scene.add_geometry(mesh, node_name=name)


def _add_cylinder(scene, p0, p1, radius, color, name):
    p0 = np.asarray(p0, dtype=np.float32)
    p1 = np.asarray(p1, dtype=np.float32)
    if np.linalg.norm(p1 - p0) < 1e-7:
        return
    mesh = trimesh.creation.cylinder(radius=radius, segment=[p0, p1], sections=8)
    mesh.visual.vertex_colors = np.tile(np.array(color, dtype=np.uint8), (len(mesh.vertices), 1))
    scene.add_geometry(mesh, node_name=name)


def export_glb(frames, club, glb_out_path):
    valid = [i for i, fr in enumerate(frames) if fr["keypoints_3d"] is not None]
    if not valid:
        raise ValueError("No valid keypoints for GLB export.")

    scene = trimesh.Scene()
    last_i = valid[-1]
    k = frames[last_i]["keypoints_3d"][:17, :3]
    c = club[last_i]

    # last-frame skeleton (solid)
    for e_idx, (a, b) in enumerate(SKELETON_EDGES):
        _add_cylinder(
            scene,
            k[H36M[a]],
            k[H36M[b]],
            radius=0.0025,
            color=(80, 180, 80, 255),
            name=f"bone_{e_idx}",
        )
    for j in range(17):
        _add_sphere(
            scene,
            k[j],
            radius=0.005,
            color=(235, 235, 235, 255),
            name=f"joint_{j}",
        )

    # club at last frame
    if c is not None:
        _add_cylinder(
            scene,
            c["butt"],
            c["club_head_proxy"],
            radius=0.003,
            color=(240, 220, 70, 255),
            name="club_shaft",
        )
        _add_sphere(
            scene,
            c["grip"],
            radius=0.006,
            color=(255, 140, 80, 255),
            name="club_grip",
        )
        _add_sphere(
            scene,
            c["club_head_proxy"],
            radius=0.007,
            color=(70, 200, 255, 255),
            name="club_head",
        )

    # motion traces (downsampled)
    for i in valid[::2]:
        ki = frames[i]["keypoints_3d"][:17, :3]
        _add_sphere(
            scene,
            ki[H36M["pelvis"]],
            radius=0.0018,
            color=(160, 160, 220, 180),
            name=f"trace_pelvis_{i}",
        )
        ci = club[i]
        if ci is not None:
            _add_sphere(
                scene,
                ci["grip"],
                radius=0.0023,
                color=(255, 140, 80, 170),
                name=f"trace_grip_{i}",
            )
            _add_sphere(
                scene,
                ci["club_head_proxy"],
                radius=0.0028,
                color=(70, 200, 255, 170),
                name=f"trace_head_{i}",
            )

    glb_out_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(str(glb_out_path))


def main():
    parser = argparse.ArgumentParser(
        description="Read MMPose JSON, synthesize proxy golf club, export annotated video."
    )
    parser.add_argument("--json", required=True, help="Path to MMPose prediction JSON")
    parser.add_argument(
        "--output",
        default=None,
        help="Output mp4 path. Default: <json_stem>_club_proxy.mp4",
    )
    parser.add_argument(
        "--glb-output",
        default=None,
        help="Output glb path. Default: <json_stem>_club_proxy.glb",
    )
    parser.add_argument("--fps", type=float, default=None, help="Output fps")
    parser.add_argument(
        "--fps-from-video",
        default="/workspace/24.mp4",
        help="Read fps from this video path when --fps is not set.",
    )
    parser.add_argument(
        "--handedness", choices=["left", "right"], default="right", help="Golfer handedness"
    )
    parser.add_argument(
        "--club-type",
        choices=["driver", "wood", "iron", "wedge"],
        default="iron",
        help="Proxy club length scale",
    )
    parser.add_argument(
        "--view-transform",
        choices=["none", "rotate-180", "flip-x", "flip-y"],
        default="rotate-180",
        help="Rotate/flip rendered view to match source direction",
    )
    parser.add_argument("--width", type=int, default=960, help="Output width")
    parser.add_argument("--height", type=int, default=720, help="Output height")
    parser.add_argument("--azim", type=float, default=0, help="3D view azimuth angle")
    parser.add_argument("--elev", type=float, default=15, help="3D view elevation angle")
    parser.add_argument("--perspective", action="store_true", help="Enable perspective projection")
    parser.add_argument("--bg-video", default=None, help="Background video for overlay rendering")
    parser.add_argument(
        "--joint-smooth-win",
        type=int,
        default=9,
        help="Temporal smoothing window for all body joints (odd integer, >=1)",
    )
    parser.add_argument(
        "--club-smooth-win",
        type=int,
        default=9,
        help="Temporal smoothing window for club direction/length (odd integer, >=1)",
    )
    args = parser.parse_args()

    json_path = Path(args.json)
    if args.output is None:
        out_path = json_path.with_name(f"{json_path.stem}_club_proxy.mp4")
    else:
        out_path = Path(args.output)
    if args.glb_output is None:
        glb_out_path = json_path.with_name(f"{json_path.stem}_club_proxy.glb")
    else:
        glb_out_path = Path(args.glb_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    glb_out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = load_mmpose_json(json_path)
    frames = smooth_keypoints_over_time(frames, win=args.joint_smooth_win)
    club = synthesize_club(
        frames,
        handedness=args.handedness,
        club_type=args.club_type,
        smooth_win=args.club_smooth_win,
    )

    fps = args.fps if args.fps is not None else try_read_fps(args.fps_from_video, fallback=30)
    render_video(
        frames,
        club,
        out_path=out_path,
        fps=fps,
        width=args.width,
        height=args.height,
        view_transform=args.view_transform,
        azim=args.azim,
        elev=args.elev,
        perspective=args.perspective,
        bg_video=args.bg_video
    )
    export_glb(frames, club, glb_out_path)

    print(f"Saved: {out_path}")
    print(f"Saved: {glb_out_path}")


if __name__ == "__main__":
    main()
