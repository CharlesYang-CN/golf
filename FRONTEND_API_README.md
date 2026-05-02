# ⛳ 高尔夫 3D 姿态分析 API 对接说明

该服务器通过 Direct TCP 提供分析服务，基于 MMPose 和专业的 3D 渲染引擎。

*   **基础 URL**: `http://80.15.7.37:48595`
*   **状态检查**: `GET /healthz`

---

## 1. 提交分析任务 (Synchronous)

该接口接收视频 URL，处理完成后直接返回 3D 模型 (.glb) 和可视化视频 (.mp4) 的链接。

*   **Endpoint**: `POST /runsync` (或 `/run`)
*   **Content-Type**: `application/json`

### 请求参数 (JSON)

```json
{
  "input": {
    "video_url": "https://example.com/your_golf_swing.mp4",
    "handedness": "right", 
    "club_type": "iron",
    "width": 960,
    "height": 720,
    "azim": 0,
    "elev": 15,
    "perspective": true,
    "overlay": true
  }
}
```

| 参数名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `video_url` | String | **必填**。视频的公开下载链接。 |
| `handedness` | String | `right` (右撇子, 默认) 或 `left` (左撇子)。 |
| `club_type` | String | 球杆类型：`driver`, `wood`, `iron`, `wedge`。 |
| `azim` | Number | 3D 视角水平旋转角度 (默认 0)。 |
| `elev` | Number | 3D 视角垂直仰角 (默认 15)。 |
| `perspective` | Boolean | 是否开启透视投影 (默认 true)。 |
| `overlay` | Boolean | **推荐**。是否将 3D 骨骼和球杆叠加在原始视频上。 |

### 成功响应

```json
{
  "ok": true,
  "job_id": "uuid-xxxx-xxxx",
  "glb_url": "http://80.15.7.37:48595/artifacts/uuid/24_club_proxy.glb",
  "mp4_url": "http://80.15.7.37:48595/artifacts/uuid/24_club_proxy.mp4",
  "json_url": "http://80.15.7.37:48595/artifacts/uuid/24.json",
  "meta": {
    "fps": 30,
    "frames": 218,
    "input_video": "..."
  }
}
```

---

## 2. 获取结果文件 (Download)

使用响应中返回的 URL 直接进行下载或展示：

*   **GLB 模型**: 工业标准 3D 格式，可直接用于 Three.js, Babylon.js 或 `<model-viewer>`。
*   **MP4 视频**: 包含专业级 3D 骨骼渲染与球杆轨迹的可视化结果。
*   **JSON 数据**: 包含每一帧的完整 3D 坐标数据。

---

## 3. 开发建议

1.  **处理耗时 (Latency)**:
    姿态估计是计算密集型任务。处理时间通常为视频长度的 3-5 倍。请在前端设置足够的 `timeout`（建议至少 120 秒）并显示进度加载状态。

2.  **文件存储**:
    生成的 `artifacts` 在服务器上是持久化的。你可以通过 `job_id` 随时找回之前分析过的文件。

3.  **跨域支持 (CORS)**:
    服务器已配置 `Access-Control-Allow-Origin: *`，支持 Web 端直接发起跨域请求。

4.  **关于视频上传**:
    目前 API 接受 URL。如果用户是本地上传视频，请前端先将视频存入云存储（如 AWS S3, 阿里云 OSS），然后将获取到的公网 URL 传给此 API。

---

## 4. 常见问题 (FAQ)

*   **Q: 为什么返回的链接无法访问？**
    A: 请确保 Pod 处于运行状态，且 `48595` 端口已在 RunPod 的 "TCP Port Mapping" 中正确开启。

*   **Q: 想要不同的 3D 视角？**
    A: 修改 `azim` (左右旋转) 和 `elev` (上下旋转) 参数重新提交即可。
