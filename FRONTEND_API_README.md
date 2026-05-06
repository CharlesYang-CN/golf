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
    "meta": {
      "input_video": "/tmp/golf_job_xxx/input.mp4",
      "pred_json": "/tmp/golf_job_xxx/outputs/predictions/input.json",
      "vis_video": "/tmp/golf_job_xxx/outputs/visualization/input.mp4",
      "club_video": "/tmp/golf_job_xxx/outputs/visualization/input_club_proxy.mp4",
      "club_glb": "/tmp/golf_job_xxx/outputs/visualization/input_club_proxy.glb",
      "fps": 5,
      "frames": 5
    }
  }
}
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

const glbBase64 = result.output.glb_base64;
const glbBytes = Uint8Array.from(atob(glbBase64), (char) =>
  char.charCodeAt(0)
);
const glbBlob = new Blob([glbBytes], { type: "model/gltf-binary" });
const glbUrl = URL.createObjectURL(glbBlob);
```

`glbUrl` can be passed to Three.js `GLTFLoader`, Babylon.js, or `<model-viewer>`.

## Request Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `video_url` | string | Yes | - | Publicly downloadable MP4 URL |
| `handedness` | string | No | `right` | `right` or `left` |
| `club_type` | string | No | `iron` | `driver`, `wood`, `iron`, or `wedge` |
| `view_transform` | string | No | `rotate-180` | `none`, `rotate-180`, `flip-x`, or `flip-y` |
| `joint_smooth_win` | number | No | `11` | Joint smoothing window |
| `club_smooth_win` | number | No | `11` | Club smoothing window |

## Notes

* `prompt` is not used by this handler. Send `input.video_url`.
* The video URL must be directly downloadable by a RunPod worker.
* GitHub raw MP4 URLs have been verified to work.
* Some stock video hosts may return `403 Forbidden` from RunPod workers because of hotlink protection, Cloudflare checks, or cloud IP restrictions.
* The RunPod handler returns `glb_base64`, not a public `glb_url`. If a persistent URL is needed, decode the base64 and upload the GLB to your own object storage.
