# 使用 RunPod 官方推荐的 PyTorch 基础镜像，确保 CUDA 11.8 环境一致
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# 安装系统依赖
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# 安装 OpenMMLab 核心依赖
# 使用官方预编译的 MMCV 轮子以加快构建速度并确保稳定性
RUN pip install --no-cache-dir mmengine==0.10.7
RUN pip install --no-cache-dir mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
RUN pip install --no-cache-dir mmpose==1.3.2

# 安装项目特定的其他依赖
RUN pip install --no-cache-dir "runpod~=1.7.6" "trimesh>=4.0.0" "matplotlib>=3.8.4" "opencv-python"

# 拷贝工作目录下的所有核心代码
COPY run_golf_3d_whole_image.py /workspace/run_golf_3d_whole_image.py
COPY render_club_from_json.py /workspace/render_club_from_json.py
COPY runpod_handler.py /workspace/runpod_handler.py
COPY test_input.json /workspace/test_input.json

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 设置 Serverless 入口程序
CMD ["python", "-u", "/workspace/runpod_handler.py"]
