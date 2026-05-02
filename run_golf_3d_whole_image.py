import argparse
import json
from pathlib import Path
import sys

from render_club_from_json import (
    export_glb,
    load_mmpose_json,
    render_video,
    smooth_keypoints_over_time,
    synthesize_club,
    try_read_fps,
)


def run_pipeline(
    input_path,
    pred_out_dir="/workspace/outputs/predictions",
    vis_out_dir="/workspace/outputs/visualization",
    device="cuda:0",
    handedness="right",
    club_type="iron",
    view_transform="rotate-180",
    width=960,
    height=720,
    joint_smooth_win=9,
    club_smooth_win=9,
    pose_model="human",
    pose3d_model="motionbert_dstformer-ft-243frm_8xb32-120e_h36m",
    azim=0,
    elev=15,
    perspective=False,
    overlay=False,
):
    """
    Golf 3D swing analysis pipeline with improved 3D pose estimation.
    """
    if Path("/workspace/mmpose").exists():
        sys.path.insert(0, "/workspace/mmpose")
    from mmpose.apis import MMPoseInferencer

    input_path = Path(input_path)
    pred_out_dir = Path(pred_out_dir)
    vis_out_dir = Path(vis_out_dir)
    pred_out_dir.mkdir(parents=True, exist_ok=True)
    vis_out_dir.mkdir(parents=True, exist_ok=True)

    inferencer = MMPoseInferencer(
        pose2d=pose_model,
        pose3d=pose3d_model,
        det_model="whole_image",
        device=device,
    )

    for _ in inferencer(
        str(input_path),
        pred_out_dir=str(pred_out_dir),
        vis_out_dir=str(vis_out_dir),
    ):
        pass

    stem = input_path.stem
    pred_json = pred_out_dir / f"{stem}.json"
    if not pred_json.exists():
        raise FileNotFoundError(f"Prediction JSON not found: {pred_json}")

    club_mp4 = vis_out_dir / f"{stem}_club_proxy.mp4"
    club_glb = vis_out_dir / f"{stem}_club_proxy.glb"

    frames = load_mmpose_json(pred_json)
    frames = smooth_keypoints_over_time(frames, win=joint_smooth_win)
    club = synthesize_club(
        frames,
        handedness=handedness,
        club_type=club_type,
        smooth_win=club_smooth_win,
    )
    fps = try_read_fps(str(input_path), fallback=30)
    
    bg_video = str(input_path) if overlay else None
    
    render_video(
        frames,
        club,
        out_path=club_mp4,
        fps=fps,
        width=width,
        height=height,
        view_transform=view_transform,
        azim=azim,
        elev=elev,
        perspective=perspective,
        bg_video=bg_video
    )
    export_glb(frames, club, club_glb)

    return {
        "input_video": str(input_path),
        "pred_json": str(pred_json),
        "vis_video": str(vis_out_dir / input_path.name),
        "club_video": str(club_mp4),
        "club_glb": str(club_glb),
        "fps": fps,
        "frames": len(frames),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run pose estimation on video and export club-overlay mp4 + glb."
    )
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--pred-out-dir", default="/workspace/outputs/predictions")
    parser.add_argument("--vis-out-dir", default="/workspace/outputs/visualization")
    parser.add_argument("--handedness", choices=["left", "right"], default="right")
    parser.add_argument("--club-type", choices=["driver", "wood", "iron", "wedge"], default="iron")
    parser.add_argument(
        "--view-transform",
        choices=["none", "rotate-180", "flip-x", "flip-y"],
        default="rotate-180",
    )
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--azim", type=float, default=0)
    parser.add_argument("--elev", type=float, default=15)
    parser.add_argument("--perspective", action="store_true")
    parser.add_argument("--overlay", action="store_true", help="Overlay 3D on original video")
    parser.add_argument("--joint-smooth-win", type=int, default=11)
    parser.add_argument("--club-smooth-win", type=int, default=11)
    parser.add_argument(
        "--pose-model",
        default="human",
        help="2D pose detector model (default: human - MMPose standard)"
    )
    parser.add_argument(
        "--pose3d-model",
        default="motionbert_dstformer-ft-243frm_8xb32-120e_h36m",
        help="3D pose model (default: motionbert_dstformer for high accuracy)"
    )
    args = parser.parse_args()

    result = run_pipeline(
        input_path=args.input,
        pred_out_dir=args.pred_out_dir,
        vis_out_dir=args.vis_out_dir,
        device=args.device,
        handedness=args.handedness,
        club_type=args.club_type,
        view_transform=args.view_transform,
        width=args.width,
        height=args.height,
        joint_smooth_win=args.joint_smooth_win,
        club_smooth_win=args.club_smooth_win,
        pose_model=args.pose_model,
        pose3d_model=args.pose3d_model,
        azim=args.azim,
        elev=args.elev,
        perspective=args.perspective,
        overlay=args.overlay,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
