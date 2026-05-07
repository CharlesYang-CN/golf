# Golf 3D Analysis API - Frontend Integration

This service runs on RunPod Serverless. The frontend sends a public video URL and receives a `glb_base64` result that can be decoded into a GLB blob for rendering.

## Endpoint

* **Endpoint ID**: `dbjmlmqpt4563g`
* **Sync URL**: `https://api.runpod.ai/v2/dbjmlmqpt4563g/runsync`
* **Async URL**: `https://api.runpod.ai/v2/dbjmlmqpt4563g/run`
* **Status URL**: `https://api.runpod.ai/v2/dbjmlmqpt4563g/status/{job_id}`
* **Auth header**: `Authorization: Bearer YOUR_RUNPOD_API_KEY`

## Verified Test Command

```bash
curl -X POST https://api.runpod.ai/v2/dbjmlmqpt4563g/runsync \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_RUNPOD_API_KEY' \
  -d '{
    "input": {
      "video_url": "https://raw.githubusercontent.com/open-mmlab/mmpose/main/demo/resources/demo.mp4",
      "handedness": "right",
      "club_type": "iron",
      "view_transform": "rotate-180",
      "joint_smooth_win": 11,
      "club_smooth_win": 11
    }
  }'
```

Expected successful response:

```json
{
  "status": "COMPLETED",
  "output": {
    "ok": true,
    "glb_base64": "Z2xURg...",
    "pred_json_base64": "W3siZnJhbW...",
    "meta": {
      "fps": 25,
      "frames": 250
    }
  }
}
```

### `pred_json_base64` Structure (for full-body swing animation)

Decode with `JSON.parse(atob(pred_json_base64))` to get per-frame 3D keypoints:

```json
[
  {
    "frame_id": 0,
    "instances": [
      {
        "keypoints": [[x,y,z], [x,y,z], ...17 joints total],
        "keypoint_scores": [1.0, 1.0, ...17 scores]
      }
    ]
  },
  ...
]
```

**17 H36M joints (index → name):**

| Index | Name | Index | Name |
|:---|:---|:---|:---|
| 0 | pelvis | 9 | neck |
| 1 | r_hip | 10 | head |
| 2 | r_knee | 11 | l_shoulder |
| 3 | r_ankle | 12 | l_elbow |
| 4 | l_hip | 13 | l_wrist |
| 5 | l_knee | 14 | r_shoulder |
| 6 | l_ankle | 15 | r_elbow |
| 7 | spine | 16 | r_wrist |
| 8 | thorax | | |

Coordinates are in meters. Use `keypoint_scores` to filter low-confidence joints.
```

## Frontend Example

```ts
const RUNPOD_ENDPOINT =
  "https://api.runpod.ai/v2/dbjmlmqpt4563g/runsync";

const response = await fetch(RUNPOD_ENDPOINT, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${process.env.NEXT_PUBLIC_RUNPOD_API_KEY}`,
  },
  body: JSON.stringify({
    input: {
      video_url: "https://your-public-video-url/video.mp4",
      handedness: "right",
      club_type: "iron",
      view_transform: "rotate-180",
      joint_smooth_win: 11,
      club_smooth_win: 11,
    },
  }),
});

const result = await response.json();

if (result.status !== "COMPLETED" || !result.output?.ok) {
  throw new Error(result.error || "Golf analysis failed");
}

// 1. Static 3D model (last-frame skeleton + club)
const glbBase64 = result.output.glb_base64;
const glbBytes = Uint8Array.from(atob(glbBase64), (char) =>
  char.charCodeAt(0)
);
const glbBlob = new Blob([glbBytes], { type: "model/gltf-binary" });
const glbUrl = URL.createObjectURL(glbBlob);

// 2. Per-frame skeleton animation data
const predJsonBase64 = result.output.pred_json_base64;
const predJson = JSON.parse(atob(predJsonBase64));
// predJson is Array<{ frame_id, instances: [{ keypoints: number[17][3], keypoint_scores: number[17] }] }>

// Drive Three.js skeleton animation frame by frame:
predJson.forEach((frame) => {
  const kpts = frame.instances[0].keypoints; // 17 joints × [x,y,z]
  // Apply to SkeletonHelper / Bone positions...
});
```

`glbUrl` can be passed to Three.js `GLTFLoader`, Babylon.js, or `<model-viewer>`.

`pred_json_base64` gives you the full motion data to animate a 17-joint skeleton across all frames.

## Request Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `video_url` | string | Yes | - | Publicly downloadable MP4 URL |
| `handedness` | string | No | `right` | `right` or `left` |
| `club_type` | string | No | `iron` | `driver`, `wood`, `iron`, or `wedge` |
| `view_transform` | string | No | `rotate-180` | `none`, `rotate-180`, `flip-x`, or `flip-y` |
| `joint_smooth_win` | number | No | `11` | Joint smoothing window |
| `club_smooth_win` | number | No | `11` | Club smoothing window |
| `pose_model` | string | No | `human` | 2D pose model |
| `pose3d_model` | string | No | `motionbert_dstformer...` | 3D pose model |
| `include_mp4_base64` | boolean | No | `false` | Set `true` to also get `mp4_base64` in response |

## Response Fields

| Field | Type | Always | Description |
|:---|:---|:---|:---|
| `ok` | boolean | Yes | `true` on success |
| `glb_base64` | string | Yes | Static GLB model (base64) — last-frame skeleton + club + motion traces |
| `pred_json_base64` | string | Yes | Per-frame 3D keypoints (base64 JSON) — 17 joints × 3D per frame |
| `mp4_base64` | string | No | Annotated MP4 video (only when `include_mp4_base64=true`) |
| `meta.fps` | number | Yes | Video frame rate |
| `meta.frames` | number | Yes | Total frame count |

## Notes

* `prompt` is not used by this handler. Send `input.video_url`.
* The video URL must be directly downloadable by a RunPod worker.
* GitHub raw MP4 URLs have been verified to work.
* Some stock video hosts may return `403 Forbidden` from RunPod workers because of hotlink protection, Cloudflare checks, or cloud IP restrictions.
* `pred_json_base64` is always returned (~0.8 MB for 250 frames). Decode with `JSON.parse(atob(...))`.
* `glb_base64` provides a static snapshot of the last frame. For full-body swing animation, use `pred_json_base64`.
