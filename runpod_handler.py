import base64
import tempfile
import urllib.request
from pathlib import Path

from run_golf_3d_whole_image import run_pipeline


def _download(url: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r:
        out_path.write_bytes(r.read())


def handler(event):
    payload = event.get("input", {}) if isinstance(event, dict) else {}
    video_path = payload.get("video_path")
    video_url = payload.get("video_url")
    if not video_path and not video_url:
        return {"error": "Provide input.video_path or input.video_url"}

    with tempfile.TemporaryDirectory(prefix="golf_job_") as tmp:
        work = Path(tmp)
        if video_url:
            video_file = work / "input.mp4"
            _download(video_url, video_file)
        else:
            video_file = Path(video_path)

        out_root = work / "outputs"
        result = run_pipeline(
            input_path=str(video_file),
            pred_out_dir=str(out_root / "predictions"),
            vis_out_dir=str(out_root / "visualization"),
            device=payload.get("device", "cuda:0"),
            handedness=payload.get("handedness", "right"),
            club_type=payload.get("club_type", "iron"),
            view_transform=payload.get("view_transform", "rotate-180"),
            width=int(payload.get("width", 960)),
            height=int(payload.get("height", 720)),
            joint_smooth_win=int(payload.get("joint_smooth_win", 11)),
            club_smooth_win=int(payload.get("club_smooth_win", 11)),
            pose_model=payload.get("pose_model", "human"),
            pose3d_model=payload.get("pose3d_model", "motionbert_dstformer-ft-243frm_8xb32-120e_h36m"),
        )

        glb_bytes = Path(result["club_glb"]).read_bytes()
        response = {
            "ok": True,
            "meta": result,
            "glb_base64": base64.b64encode(glb_bytes).decode("ascii"),
        }
        if payload.get("include_mp4_base64", False):
            mp4_bytes = Path(result["club_video"]).read_bytes()
            response["mp4_base64"] = base64.b64encode(mp4_bytes).decode("ascii")
        return response


if __name__ == "__main__":
    try:
        import runpod
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "runpod package not found. In RunPod serverless image this should exist."
        ) from e
    runpod.serverless.start({"handler": handler})
