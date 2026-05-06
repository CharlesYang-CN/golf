#!/bin/bash
# 高尔夫 3D 姿态分析环境一键配置脚本 (FastAPI + Gemini 增强版)

set -e

echo "🚀 开始配置环境 (FastAPI + Gemini 增强版)..."

# 1. 系统依赖
if command -v apt-get &> /dev/null; then
    echo "📦 安装系统依赖 (libGL, libglib)..."
    if command -v sudo &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0 curl
    else
        apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 curl
    fi
fi

# 2. 基础 Python 兼容环境
echo "🐍 配置 Python 核心包 (NumPy/Matplotlib/OpenCV 兼容版)..."
pip install --no-cache-dir "numpy<2" "matplotlib<3.9" "opencv-python<4.10"

# 3. 现代 Web 框架 (FastAPI)
echo "🌐 安装 FastAPI 服务组件..."
pip install --no-cache-dir fastapi uvicorn httpx pydantic

# 5. OpenMMLab 系列组件
echo "📚 安装 OpenMMLab AI 引擎 (MMEngine, MMCV, MMDet, MMPose)..."
pip install --no-cache-dir mmengine==0.10.7
pip install --no-cache-dir mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
pip install --no-cache-dir mmdet==3.3.0
pip install --no-cache-dir mmpose==1.3.2

# 6. 其他工具
echo "🛠️ 安装配套工具 (RunPod, Trimesh)..."
pip install --no-cache-dir "runpod~=1.7.6" "trimesh>=4.0.0"

echo ""
echo "✅ 环境配置完成！"
echo "------------------------------------------------"
echo "启动服务: python fastapi_server.py"
echo "访问接口文档: http://localhost:8000/docs"
echo "Gemini SDK 已安装，你可以开始编写 AI 分析逻辑。"
echo "------------------------------------------------"
