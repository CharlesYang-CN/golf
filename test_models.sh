#!/bin/bash
# 测试不同模型配置的脚本

set -e

VIDEO_PATH="${1:-.workspace/24.mp4}"
PORT=48723
HOST="localhost"

echo "🎬 高尔夫3D模型测试脚本"
echo "======================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_test() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 检查视频文件
if [ ! -f "$VIDEO_PATH" ]; then
    echo "❌ 错误: 视频文件不存在: $VIDEO_PATH"
    exit 1
fi

echo "📹 使用视频: $VIDEO_PATH"
echo ""

# 测试 1: 推荐配置 (RTMPose-L + RTMW3D)
print_test "测试 1️⃣ : RTMPose-L + RTMW3D (推荐)"
python /workspace/run_golf_3d_whole_image.py \
    --input "$VIDEO_PATH" \
    --pose-model rtmpose-l \
    --pose3d-model rtmw3d-x \
    --vis-out-dir /workspace/outputs/test1_rtmpose_l

echo -e "${GREEN}✓ 测试 1 完成${NC}\n"

# 测试 2: 快速配置 (RTMPose-M + RTMW3D)
print_test "测试 2️⃣ : RTMPose-M + RTMW3D (快速)"
python /workspace/run_golf_3d_whole_image.py \
    --input "$VIDEO_PATH" \
    --pose-model rtmpose-m \
    --pose3d-model rtmw3d-x \
    --vis-out-dir /workspace/outputs/test2_rtmpose_m

echo -e "${GREEN}✓ 测试 2 完成${NC}\n"

# 测试 3: 最高精度配置 (ViTPose++ + RTMW3D)
print_test "测试 3️⃣ : ViTPose++ + RTMW3D (最高精度)"
python /workspace/run_golf_3d_whole_image.py \
    --input "$VIDEO_PATH" \
    --pose-model vitpose++ \
    --pose3d-model rtmw3d-x \
    --vis-out-dir /workspace/outputs/test3_vitpose

echo -e "${GREEN}✓ 测试 3 完成${NC}\n"

# 测试 4: 原始配置 (Human + MotionBERT)
print_test "测试 4️⃣ : Human + MotionBERT (原始)"
python /workspace/run_golf_3d_whole_image.py \
    --input "$VIDEO_PATH" \
    --pose-model human \
    --pose3d-model motionbert_dstformer-ft-243frm_8xb32-120e_h36m \
    --vis-out-dir /workspace/outputs/test4_original

echo -e "${GREEN}✓ 测试 4 完成${NC}\n"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ 所有模型测试完成！${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 结果对比:"
echo "- 测试 1 (推荐): /workspace/outputs/test1_rtmpose_l"
echo "- 测试 2 (快速): /workspace/outputs/test2_rtmpose_m"
echo "- 测试 3 (精度): /workspace/outputs/test3_vitpose"
echo "- 测试 4 (原始): /workspace/outputs/test4_original"
echo ""
echo "💡 建议: 比较各输出目录下的 .glb 和 .mp4 文件效果"
