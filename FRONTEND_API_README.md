# Golf 3D Analysis API (FastAPI) - 前端对接文档

本文档介绍如何对接基于 FastAPI 的高尔夫 3D 姿态分析服务。

## 1. 基础信息
*   **API 根地址**: `http://80.15.7.37:48723`
*   **可视化交互文档**: `http://80.15.7.37:48723/docs` (Swagger UI)
*   **静态资源前缀**: `http://80.15.7.37:48723/artifacts/`

## 2. 核心接口

### 2.1 同步分析 (适合短视频/即时测试)
等待推理完成后直接返回结果。
*   **URL**: `POST /runsync`
*   **Payload**:
```json
{
  "video_url": "https://example.com/video.mp4",
  "handedness": "right",
  "club_type": "iron"
}
```
*   **Response**:
```json
{
  "ok": true,
  "job_id": "uuid-string",
  "glb_url": "http://.../artifacts/uuid/files/result.glb",
  "mp4_url": "http://.../artifacts/uuid/files/result.mp4",
  "json_url": "http://.../artifacts/uuid/files/result.json",
  "meta": { ... }
}
```

### 2.2 异步分析 (推荐用于生产环境)
立即返回 `job_id`，前端轮询状态。
*   **URL**: `POST /run_async`
*   **Payload**: 同上。
*   **Response**:
```json
{
  "ok": true,
  "job_id": "uuid-string",
  "status_url": "http://80.15.7.37:48723/status/uuid-string"
}
```

### 2.3 状态查询
查询异步任务的进度或获取结果。
*   **URL**: `GET /status/{job_id}`
*   **Response (处理中)**:
```json
{ "status": "processing" }
```
*   **Response (成功)**:
```json
{
  "status": "completed",
  "glb_url": "http://...",
  "mp4_url": "http://...",
  "json_url": "http://...",
  "meta": { ... }
}
```

## 3. 参数说明
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `video_url` | string | 否 | - | 视频下载地址 (与 video_path 二选一) |
| `video_path` | string | 否 | - | 服务器本地路径 (测试用) |
| `handedness` | string | 否 | "right" | "right" (右手) 或 "left" (左手) |
| `club_type` | string | 否 | "iron" | 球杆类型 |
| `joint_smooth_win` | int | 否 | 11 | 关节平滑系数 (推荐 11-15) |

## 4. 资源加载
生成的 `.glb` 文件可以通过标准的 3D 引擎（如 Three.js, Babylon.js 或 `<model-viewer>`）直接加载。
