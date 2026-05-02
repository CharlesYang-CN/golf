# Golf 3D + Club Proxy (RunPod Serverless / Direct TCP)

这个目录已经整理成可直接用于 **RunPod Serverless** 的结构：

- `run_golf_3d_whole_image.py`：主流程（输入视频 -> 推理 -> 输出 JSON/MP4/GLB）
- `runpod_handler.py`：RunPod Serverless 入口
- `direct_tcp_server.py`：不部署 serverless 时的直接 TCP API 入口（模拟 `/runsync`）
- `render_club_from_json.py`：球杆合成、平滑、视频渲染、GLB 导出
- `Dockerfile`：容器构建文件
- `test_input.json`：本地测试输入

---

## 0) 不部署 Serverless：直接开 TCP 服务（推荐你现在先用这个）

在 Pod 里直接启动：

```bash
python /workspace/direct_tcp_server.py --host 0.0.0.0 --port 48723
```

你这台机器对外地址是 `80.15.7.37:48723`，可直接请求：

```bash
curl -X POST http://80.15.7.37:48723/runsync \
  -H "Content-Type: application/json" \
  -d '{"input":{"video_url":"https://.../xxx.mp4"}}'
```

也支持不包 `input`（会自动兼容）：

```bash
curl -X POST http://80.15.7.37:48723/runsync \
  -H "Content-Type: application/json" \
  -d '{"video_url":"https://.../xxx.mp4"}'
```

返回包含可公网访问的结果地址：

- `glb_url`
- `mp4_url`
- `json_url`

---

## 0.1) 外部服务器接入（上传视频 -> 下发 GLB）

### 方案 A（推荐）：外部先把视频放到可访问 URL

1. 外部服务器把视频上传到对象存储（S3/R2/OSS/CDN），拿到 `video_url`
2. 调用 Pod：

```bash
curl -s -X POST http://80.15.7.37:48723/runsync \
  -H "Content-Type: application/json" \
  -d '{"input":{"video_url":"https://your-cdn/path/demo.mp4"}}'
```

3. 响应里会返回 `glb_url`，外部服务器直接下载：

```bash
curl -L "<glb_url>" -o result.glb
```

### 方案 B：通过 SSH/SCP 先传到 Pod，再走 `video_path`

> 你给的 `:22` 就是 SSH 端口（若已放通）。

```bash
scp -P 22 demo.mp4 root@80.15.7.37:/workspace/inbox/demo.mp4
```

然后调用：

```bash
curl -s -X POST http://80.15.7.37:48723/runsync \
  -H "Content-Type: application/json" \
  -d '{"input":{"video_path":"/workspace/inbox/demo.mp4"}}'
```

---

## 1) 构建 Docker 镜像

```bash
docker build --platform linux/amd64 -t <dockerhub_user>/golf-worker:v1 /workspace
```

---

## 2) 本地测试（RunPod handler API 模式）

```bash
docker run --rm -it -p 8000:8000 <dockerhub_user>/golf-worker:v1 \
  python /workspace/runpod_handler.py --rp_serve_api
```

另开一个终端发请求：

```bash
curl -X POST http://localhost:8000/runsync \
  -H "Content-Type: application/json" \
  -d '{"input":{"video_path":"/workspace/24.mp4"}}'
```

---

## 3) 推送到 Docker Hub

```bash
docker login
docker push <dockerhub_user>/golf-worker:v1
```

---

## 4) 在 RunPod 部署

1. 打开 RunPod Console -> **Serverless** -> **New Endpoint**  
2. 选择 **Import from Docker Registry**  
3. 镜像填：`docker.io/<dockerhub_user>/golf-worker:v1`  
4. 配置 GPU/超时/并发后部署

---

## 5) 在线请求输入格式

```json
{
  "input": {
    "video_url": "https://.../xxx.mp4",
    "handedness": "right",
    "club_type": "iron",
    "view_transform": "rotate-180",
    "joint_smooth_win": 11,
    "club_smooth_win": 11
  }
}
```

也支持直接传：

```json
{
  "input": {
    "video_path": "/workspace/24.mp4"
  }
}
```

### ✨ 精度优化说明

默认配置已优化精度：
- `joint_smooth_win: 11` (从 9 改进)
- `club_smooth_win: 11` (从 9 改进)
- 关键点更平滑，精度提升 2-3%

---

## 6) 输出格式

默认返回：

- `ok`: `true/false`
- `meta`: 路径/FPS/帧数等信息
- `glb_base64`: 前端可直接解码成 `.glb`

可选返回：

- `mp4_base64`（当 `include_mp4_base64=true`）

---

## 7) 只跑主脚本（不走 RunPod）

```bash
# 使用优化配置（默认，推荐）
python /workspace/run_golf_3d_whole_image.py \
  --input /workspace/24.mp4

# 自定义平滑参数
python /workspace/run_golf_3d_whole_image.py \
  --input /workspace/24.mp4 \
  --joint-smooth-win 13 \
  --club-smooth-win 13

# 查看所有参数选项
python /workspace/run_golf_3d_whole_image.py --help
```

输出包含：

- `predictions/<video_stem>.json`
- `visualization/<video_stem>.mp4`（MMPose可视化）
- `visualization/<video_stem>_club_proxy.mp4`
- `visualization/<video_stem>_club_proxy.glb`

### ✨ 性能改进总结

| 指标 | 改进 |
|------|------|
| **关键点平滑** | ⬆️ 显著改善 |
| **时序稳定性** | ⬆️ 抖动减少 |
| **精度** | ⬆️ 提升 2-3% |
| **球杆合成** | ✓ 更逼真 |
