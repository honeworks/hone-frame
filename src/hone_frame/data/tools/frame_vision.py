"""hone-frame's vision tool (change 0007), run by hone-models' `command` provider in an environment with
torch and transformers: body keypoints (ViTPose) and image embeddings (DINOv2) for the measured checks.

`request.json` (hone-models' command protocol): `prompt` names what to compute ("keypoints",
"embedding", or both, comma-separated); `inputs.references` lists the images. The answer is one small
PNG in `out_dir` whose text chunk `hone-frame` holds JSON: `{"images": [{"path", "keypoints"?: [[x, y,
score], ... 17], "embedding"?: [...]}]}`. Runs on the CPU (the GPU stays with the image models).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

POSE_MODEL = "usyd-community/vitpose-base-simple"
EMBED_MODEL = "facebook/dinov2-small"


def keypoints(paths: list[str]) -> list[list[list[float]]]:
    import torch
    from PIL import Image
    from transformers import AutoProcessor, VitPoseForPoseEstimation

    proc = AutoProcessor.from_pretrained(POSE_MODEL)
    model = VitPoseForPoseEstimation.from_pretrained(POSE_MODEL)
    found: list[list[list[float]]] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        box = [[[0, 0, image.width, image.height]]]
        with torch.no_grad():
            out = model(**proc(image, boxes=box, return_tensors="pt"))
        res = proc.post_process_pose_estimation(out, boxes=box)[0][0]
        found.append(
            [
                [float(x), float(y), float(s)]
                for (x, y), s in zip(res["keypoints"].tolist(), res["scores"].tolist(), strict=True)
            ]
        )
    return found


def embeddings(paths: list[str]) -> list[list[float]]:
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    proc = AutoImageProcessor.from_pretrained(EMBED_MODEL)
    model = AutoModel.from_pretrained(EMBED_MODEL)
    found: list[list[float]] = []
    for path in paths:
        with torch.no_grad():
            out = model(**proc(images=Image.open(path).convert("RGB"), return_tensors="pt"))
        found.append([float(v) for v in out.pooler_output[0].tolist()])
    return found


def main(request_path: str) -> int:
    from PIL import Image, PngImagePlugin

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    out_dir = Path(request["out_dir"])
    paths = [str(p) for p in request.get("inputs", {}).get("references") or []]
    wanted = {w.strip() for w in str(request.get("prompt", "")).split(",") if w.strip()}
    rows: list[dict[str, object]] = [{"path": p} for p in paths]
    if "keypoints" in wanted:
        for row, kps in zip(rows, keypoints(paths), strict=True):
            row["keypoints"] = kps
    if "embedding" in wanted:
        for row, emb in zip(rows, embeddings(paths), strict=True):
            row["embedding"] = emb
    info = PngImagePlugin.PngInfo()
    info.add_text("hone-frame", json.dumps({"images": rows}))
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "white").save(out_dir / "vision.png", pnginfo=info)
    (out_dir / "result.json").write_text(json.dumps({"files": ["vision.png"]}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
