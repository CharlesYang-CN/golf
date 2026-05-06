# 使用 RunPod 官方推荐的 PyTorch 基础镜像，确保 CUDA 11.8 环境一致
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

COPY constraints.txt /tmp/constraints.txt

# Force every pip install in this build to stay on the NumPy 1.x ABI.
ENV PIP_CONSTRAINT=/tmp/constraints.txt

# 安装系统依赖 & 删除系统级 numpy（apt 安装的 numpy 与 pip 版本冲突导致 xtcocotools ABI 不兼容）
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 \
    && apt-get remove -y python3-numpy || true \
    && rm -rf /var/lib/apt/lists/*

# 修复 numpy ABI 兼容性：先清理基础镜像/旧层中的 native 包，再在约束下重装。
RUN pip uninstall -y numpy xtcocotools pycocotools || true
RUN pip install --no-cache-dir --force-reinstall "numpy==1.26.4"

# 安装 OpenMMLab 核心依赖
# 使用官方预编译的 MMCV 轮子以加快构建速度并确保稳定性
RUN pip install --no-cache-dir mmengine==0.10.7
RUN pip install --no-cache-dir mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
RUN pip install --no-cache-dir mmdet==3.3.0 mmpose==1.3.2

# Reinstall NumPy C-extension packages after OpenMMLab so they are built/loaded
# against the pinned NumPy 1.26 ABI instead of any base-image NumPy.
RUN pip uninstall -y xtcocotools pycocotools || true
RUN pip install --no-cache-dir --no-build-isolation --force-reinstall xtcocotools==1.14.3 pycocotools==2.0.11

# 安装项目特定的其他依赖
RUN pip install --no-cache-dir "runpod~=1.7.6" "trimesh>=4.0.0" "matplotlib>=3.8.4,<3.9" "opencv-python==4.9.0.80" "fastapi" "uvicorn" "httpx" "pydantic"

# Fail the Docker build before pushing if NumPy or native MMPose deps are ABI-broken.
RUN python -c "import numpy as np; print('numpy', np.__version__, np.__file__); assert np.__version__.startswith('1.26.'); import xtcocotools._mask; from mmpose.apis import MMPoseInferencer; print('mmpose smoke test ok')"

# 拷贝工作目录下的所有核心代码
COPY run_golf_3d_whole_image.py /workspace/run_golf_3d_whole_image.py
COPY render_club_from_json.py /workspace/render_club_from_json.py
COPY runpod_handler.py /workspace/runpod_handler.py
COPY fastapi_server.py /workspace/fastapi_server.py
COPY test_input.json /workspace/test_input.json

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 设置 Serverless 入口程序
CMD ["python", "-u", "/workspace/runpod_handler.py"]
