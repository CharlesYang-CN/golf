import os
import shutil
import traceback
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from run_golf_3d_whole_image import run_pipeline

# --- 配置 ---
ARTIFACT_ROOT = Path("/workspace/public_jobs")
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Golf 3D Analysis API",
    description="基于 MMPose 的高尔夫 3D 姿态分析与球杆渲染服务",
    version="2.0.2"
)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录 (外部通过 /artifacts 访问)
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_ROOT)), name="artifacts")

# --- 数据模型 ---
class AnalysisInput(BaseModel):
    video_url: Optional[str] = Field(None, description="视频的远程下载地址")
    video_path: Optional[str] = Field(None, description="Pod 内部的视频路径")
    handedness: str = Field("right", description="选手利手: right 或 left")
    club_type: str = Field("iron", description="球杆类型: iron, driver 等")
    view_transform: str = Field("rotate-180", description="视图变换")
    joint_smooth_win: int = Field(11, description="关节平滑窗口大小")
    club_smooth_win: int = Field(11, description="球杆平滑窗口大小")
    pose_model: str = Field("human", description="2D 姿态模型")
    pose3d_model: str = Field("motionbert_dstformer-ft-243frm_8xb32-120e_h36m", description="3D 姿态模型")

class AnalysisResponse(BaseModel):
    ok: bool
    job_id: str
    glb_url: str
    mp4_url: str
    json_url: str
    meta: dict

# --- 内部工具 ---
def get_base_url(request: Request):
    # 自动获取当前访问的域名和端口
    # 优先从 Header 获取 Host 以应对 RunPod 端口映射
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        host = f"{request.url.hostname}:{request.url.port}" if request.url.port else request.url.hostname
    
    # 强制使用 http 因为 RunPod 内部转发通常是 http
    scheme = request.headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{host}"

async def download_file(url: str, dest: Path):
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            raise Exception(f"Failed to download video from {url}")
        dest.write_bytes(resp.content)

def process_video_task(job_id: str, input_data: AnalysisInput, base_url: str):
    """
    实际执行推理的任务 (同步执行，由 BackgroundTasks 调用)
    """
    try:
        job_root = ARTIFACT_ROOT / job_id
        in_dir = job_root / "input"
        out_dir = job_root / "outputs"
        pred_dir = out_dir / "predictions"
        vis_dir = out_dir / "visualization"
        
        for d in [in_dir, pred_dir, vis_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 处理输入
        if input_data.video_url:
            input_video = in_dir / "input.mp4"
            import urllib.request
            urllib.request.urlretrieve(input_data.video_url, str(input_video))
        else:
            input_video = Path(input_data.video_path)

        # 执行推理
        result = run_pipeline(
            input_path=str(input_video),
            pred_out_dir=str(pred_dir),
            vis_out_dir=str(vis_dir),
            handedness=input_data.handedness,
            club_type=input_data.club_type,
            view_transform=input_data.view_transform,
            joint_smooth_win=input_data.joint_smooth_win,
            club_smooth_win=input_data.club_smooth_win,
            pose_model=input_data.pose_model,
            pose3d_model=input_data.pose3d_model
        )

        # 整理输出到 artifacts 目录方便静态访问
        artifacts_dir = job_root / "files"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        glb_name = Path(result["club_glb"]).name
        mp4_name = Path(result["club_video"]).name
        json_name = Path(result["pred_json"]).name
        
        shutil.copy2(result["club_glb"], artifacts_dir / glb_name)
        shutil.copy2(result["club_video"], artifacts_dir / mp4_name)
        shutil.copy2(result["pred_json"], artifacts_dir / json_name)
        
        # 标记完成
        status = {
            "status": "completed",
            "glb_url": f"{base_url}/artifacts/{job_id}/files/{glb_name}",
            "mp4_url": f"{base_url}/artifacts/{job_id}/files/{mp4_name}",
            "json_url": f"{base_url}/artifacts/{job_id}/files/{json_name}",
            "meta": result
        }
        (job_root / "status.json").write_text(json.dumps(status))

    except Exception as e:
        error_msg = {"status": "failed", "error": str(e), "traceback": traceback.format_exc()}
        (ARTIFACT_ROOT / job_id / "status.json").write_text(json.dumps(error_msg))

# --- 路由 ---

@app.get("/health")
async def health():
    return {"status": "ok", "service": "golf-3d-api"}

@app.post("/runsync", response_model=AnalysisResponse)
async def run_sync(request: Request):
    """
    同步接口：上传后等待处理完成才返回结果 (支持嵌套 input 或扁平格式)
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body. Did you mean to use /upload_run for file uploads?")

    # 自动解析格式
    input_dict = body.get("input", body)
    try:
        input_data = AnalysisInput(**input_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input format: {str(e)}")

    job_id = str(uuid.uuid4())
    base_url = get_base_url(request)
    
    try:
        job_root = ARTIFACT_ROOT / job_id
        in_dir = job_root / "input"
        in_dir.mkdir(parents=True, exist_ok=True)

        if input_data.video_url:
            input_video = in_dir / "input.mp4"
            import urllib.request
            urllib.request.urlretrieve(input_data.video_url, str(input_video))
        elif input_data.video_path:
            input_video = Path(input_data.video_path)
            if not input_video.exists():
                raise HTTPException(status_code=400, detail=f"File not found: {input_data.video_path}")
        else:
            raise HTTPException(status_code=400, detail="Either video_url or video_path must be provided")

        result = run_pipeline(
            input_path=str(input_video),
            pred_out_dir=str(job_root / "outputs" / "predictions"),
            vis_out_dir=str(job_root / "outputs" / "visualization"),
            handedness=input_data.handedness,
            club_type=input_data.club_type,
            view_transform=input_data.view_transform,
            joint_smooth_win=input_data.joint_smooth_win,
            club_smooth_win=input_data.club_smooth_win,
            pose_model=input_data.pose_model,
            pose3d_model=input_data.pose3d_model
        )

        artifacts_dir = job_root / "files"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result["club_glb"], artifacts_dir / Path(result["club_glb"]).name)
        shutil.copy2(result["club_video"], artifacts_dir / Path(result["club_video"]).name)
        shutil.copy2(result["pred_json"], artifacts_dir / Path(result["pred_json"]).name)

        return {
            "ok": True,
            "job_id": job_id,
            "glb_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['club_glb']).name}",
            "mp4_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['club_video']).name}",
            "json_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['pred_json']).name}",
            "meta": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")

@app.post("/upload_run", response_model=AnalysisResponse)
async def upload_run(
    request: Request,
    file: UploadFile = File(...),
    handedness: str = Form("right"),
    club_type: str = Form("iron"),
    view_transform: str = Form("rotate-180"),
    joint_smooth_win: int = Form(11),
    club_smooth_win: int = Form(11),
    pose_model: str = Form("human"),
    pose3d_model: str = Form("motionbert_dstformer-ft-243frm_8xb32-120e_h36m")
):
    """
    文件上传接口：直接 POST 视频文件进行推理
    """
    job_id = str(uuid.uuid4())
    base_url = get_base_url(request)
    job_root = ARTIFACT_ROOT / job_id
    in_dir = job_root / "input"
    in_dir.mkdir(parents=True, exist_ok=True)
    
    # 清理文件名中的特殊字符
    safe_filename = "".join([c if c.isalnum() or c in "._-" else "_" for c in file.filename])
    input_video = in_dir / safe_filename
    
    with input_video.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        result = run_pipeline(
            input_path=str(input_video),
            pred_out_dir=str(job_root / "outputs" / "predictions"),
            vis_out_dir=str(job_root / "outputs" / "visualization"),
            handedness=handedness,
            club_type=club_type,
            view_transform=view_transform,
            joint_smooth_win=joint_smooth_win,
            club_smooth_win=club_smooth_win,
            pose_model=pose_model,
            pose3d_model=pose3d_model
        )

        artifacts_dir = job_root / "files"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result["club_glb"], artifacts_dir / Path(result["club_glb"]).name)
        shutil.copy2(result["club_video"], artifacts_dir / Path(result["club_video"]).name)
        shutil.copy2(result["pred_json"], artifacts_dir / Path(result["pred_json"]).name)

        return {
            "ok": True,
            "job_id": job_id,
            "glb_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['club_glb']).name}",
            "mp4_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['club_video']).name}",
            "json_url": f"{base_url}/artifacts/{job_id}/files/{Path(result['pred_json']).name}",
            "meta": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")


@app.post("/run_async")
async def run_async(request: Request, input_data: AnalysisInput, background_tasks: BackgroundTasks):
    """
    异步接口：立即返回 job_id，后台处理
    """
    job_id = str(uuid.uuid4())
    base_url = get_base_url(request)
    
    # 初始化状态
    job_root = ARTIFACT_ROOT / job_id
    job_root.mkdir(parents=True, exist_ok=True)
    import json
    (job_root / "status.json").write_text(json.dumps({"status": "processing"}))
    
    background_tasks.add_task(process_video_task, job_id, input_data, base_url)
    
    return {
        "ok": True,
        "job_id": job_id,
        "status_url": f"{base_url}/status/{job_id}"
    }

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    status_file = ARTIFACT_ROOT / job_id / "status.json"
    if not status_file.exists():
        return {"status": "not_found"}
    import json
    return json.loads(status_file.read_text())

if __name__ == "__main__":
    # 启动服务器，监听 8000 端口
    uvicorn.run(app, host="0.0.0.0", port=8000)
