import argparse
import json
import mimetypes
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from run_golf_3d_whole_image import run_pipeline


ARTIFACT_ROOT = Path("/workspace/public_jobs")
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


def _download(url: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r:
        out_path.write_bytes(r.read())


def _to_int(payload, key, default):
    try:
        return int(payload.get(key, default))
    except Exception:
        return int(default)


class _Handler(BaseHTTPRequestHandler):
    server_version = "GolfTCP/1.0"

    def _set_common_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._set_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            self._send_json(404, {"error": "File not found"})
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self._set_common_headers()
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_common_headers()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "golf-direct-tcp",
                    "endpoints": ["POST /run", "POST /runsync", "GET /artifacts/<job_id>/<file>"],
                },
            )
            return
        if self.path.startswith("/artifacts/"):
            rel = self.path[len("/artifacts/") :].lstrip("/")
            safe = (ARTIFACT_ROOT / rel).resolve()
            if ARTIFACT_ROOT.resolve() not in safe.parents and safe != ARTIFACT_ROOT.resolve():
                self._send_json(400, {"error": "Invalid artifact path"})
                return
            self._send_file(safe)
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path not in ("/run", "/runsync"):
            self._send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                self._send_json(400, {"error": "Empty body"})
                return
            raw = self.rfile.read(length)
            req = json.loads(raw.decode("utf-8"))

            if not isinstance(req, dict):
                self._send_json(400, {"error": "JSON body must be an object"})
                return

            if "input" not in req:
                req = {"input": req}

            payload = req.get("input", {})
            video_url = payload.get("video_url")
            video_path = payload.get("video_path")
            if not video_url and not video_path:
                self._send_json(400, {"error": "Provide input.video_url (recommended) or input.video_path"})
                return

            job_id = str(uuid4())
            job_root = ARTIFACT_ROOT / job_id
            in_dir = job_root / "input"
            out_dir = job_root / "outputs"
            pred_dir = out_dir / "predictions"
            vis_dir = out_dir / "visualization"
            in_dir.mkdir(parents=True, exist_ok=True)
            pred_dir.mkdir(parents=True, exist_ok=True)
            vis_dir.mkdir(parents=True, exist_ok=True)

            if video_url:
                input_video = in_dir / "input.mp4"
                _download(video_url, input_video)
            else:
                input_video = Path(video_path)

            result = run_pipeline(
                input_path=str(input_video),
                pred_out_dir=str(pred_dir),
                vis_out_dir=str(vis_dir),
                device=payload.get("device", "cuda:0"),
                handedness=payload.get("handedness", "right"),
                club_type=payload.get("club_type", "iron"),
                view_transform=payload.get("view_transform", "rotate-180"),
                width=_to_int(payload, "width", 960),
                height=_to_int(payload, "height", 720),
                joint_smooth_win=_to_int(payload, "joint_smooth_win", 11),
                club_smooth_win=_to_int(payload, "club_smooth_win", 11),
                pose_model=payload.get("pose_model", "human"),
                pose3d_model=payload.get("pose3d_model", "motionbert_dstformer-ft-243frm_8xb32-120e_h36m"),
            )

            artifacts = job_root / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            glb_path = artifacts / Path(result["club_glb"]).name
            mp4_path = artifacts / Path(result["club_video"]).name
            json_path = artifacts / Path(result["pred_json"]).name
            copy2(result["club_glb"], glb_path)
            copy2(result["club_video"], mp4_path)
            copy2(result["pred_json"], json_path)

            host = self.headers.get("Host", f"{self.server.server_address[0]}:{self.server.server_address[1]}")
            base = f"http://{host}"
            response = {
                "ok": True,
                "job_id": job_id,
                "meta": result,
                "glb_url": f"{base}/artifacts/{job_id}/{glb_path.name}",
                "mp4_url": f"{base}/artifacts/{job_id}/{mp4_path.name}",
                "json_url": f"{base}/artifacts/{job_id}/{json_path.name}",
            }
            self._send_json(200, response)
        except Exception as e:
            self._send_json(
                500,
                {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )


def main():
    parser = argparse.ArgumentParser(description="Direct TCP server with RunPod-like /runsync API.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"Serving on http://{args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
