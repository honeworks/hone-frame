# Tools and libraries that could help

Open-source models and Python libraries for each stage, found while looking for things like the pose
library (mannequin references), which turned out to fix poses. Researched 2026-10-03; licenses and
memory needs change, so check again before adopting one. "8 GB?" means the owner's 8 GB laptop GPU;
the disk had about 5–6 GB free at the time, so anything above about 1 GB needs space first.

Every model call goes through hone-models (the family rule), so a model used at generation time needs a
hone-models entry (usually a ComfyUI workflow). CPU-side analysis libraries (pose keypoints, hashes,
embeddings) are checks, not model calls in the hone-models sense, and can be used directly; that
distinction should be confirmed in the design.

**License rule to decide:** if hone-frame must stay usable commercially, keep to MIT / Apache / BSD and
treat the non-commercial or regionally restricted ones (marked ⚠) as optional extras.

## Before generating: references built in code

| Tool | What it gives us | 8 GB? | License | Status |
|---|---|---|---|---|
| Our own 3D mannequins (trimesh + pyrender, a jointed body we build) | exact pose and exact camera every time; height and build from the character's parameters | CPU | MIT | idea |
| [SMPL-X](https://pypi.org/project/smplfitter/) body model | realistic body shapes from height and weight | CPU | ⚠ model non-commercial | alternative to the above |
| [TripoSR](https://github.com/VAST-AI-Research/TripoSR) | a 3D mesh from one object or animal image, then true front, side, back and top views as references (the bow, lasso and Rakhsh problem) | ~6 GB | MIT | to test |
| [Hunyuan3D-2mini](https://huggingface.co/tencent/Hunyuan3D-2mini) | better 3D shapes, ~5 GB | ~5 GB | ⚠ community license excluding EU, UK, South Korea | to test if accepted |
| [Stable Virtual Camera (SEVA)](https://www.alphaxiv.org/abs/2503.14489) | new consistent views of a place along a camera path | 1.3B, test | check license | to test |
| [ViewCrafter](https://github.com/Drexubery/ViewCrafter) | same, higher quality | 23.5 GB, no | | out of reach |
| Depth Anything V2 (small, already downloaded) | depth maps of places; reprojected for new consistent viewpoints; depth conditioning | ~1 GB | Apache (small) | to test |
| py360convert + one 360° panorama of a place | any number of matching place views cut from one image | CPU | MIT | to test |
| [rtmlib](https://github.com/Tau-J/rtmlib) (DWPose / RTMPose, no mmcv) | body, hand and foot keypoints from any image: take a pose from a photo the person likes | CPU | Apache | to test |
| palette extraction (scikit-learn k-means) | a measured colour palette per character and object, as a swatch reference and a check | CPU | BSD | idea |

## During generation: control

| Tool | What it gives | Notes |
|---|---|---|
| [Qwen-Image ControlNet Union (InstantX)](https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union) | real pose, depth, canny and soft-edge control for Qwen-Image: the mannequin skeleton or a place's depth map followed exactly | ComfyUI support exists; size to check against the disk |
| FLUX.2 klein depth through its reference slot ([node](https://comfy.icu/node/FluxKleinControlNetImg2Img)) | depth-guided edits on the model we already run | klein has no real ControlNet; depth via Depth Anything is the mode said to work |
| [FLUX.2-dev Fun ControlNet Union](https://huggingface.co/alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union) | pose, depth, canny … for FLUX.2-dev | FLUX.2-dev is too large for 8 GB |
| [UNO](https://github.com/bytedance/UNO) / [USO](https://bytedance.github.io/USO/) (ByteDance) | subject and identity consistency; style plus subject together | built on FLUX.1-dev (large); later |
| Qwen-Image-Edit Multiple-Angles LoRA (in use) | camera angles for edits | already in the final profile |

## After generating: measured checks (instead of judge opinions where possible)

| Tool | What it measures | License |
|---|---|---|
| rtmlib (DWPose) | the pose matches the mannequin's keypoints; the image is not mirrored; the feet point the way the body faces (the foot the 7B judge cannot see); hand keypoints | Apache |
| imagehash | near-duplicate views: reject "side" when it equals "front" | BSD |
| DINOv2 (small, already downloaded) | the same object or place as the approved image (an axe instead of the ox-head mace scores low) | Apache |
| [facenet-pytorch](https://github.com/timesler/facenet-pytorch) | the same face across expressions and views, as a number | MIT |
| InsightFace | better face identity | ⚠ [models non-commercial](https://www.insightface.ai/solutions/face-recognition-licensing) |
| MediaPipe face landmarks and segmentation | where a mark, an armlet or a beard is; beard region and length | Apache |
| [SAM 2](https://github.com/huggingface/segment-anything-2) | general segmentation: background, garments, objects | Apache |
| BiRefNet or rembg | background check and clean cut-outs | MIT |
| [HandCraft](https://arxiv.org/html/2411.04332v1), [HandRefiner](https://arxiv.org/html/2311.17957v2) | detect and repair malformed hands | research code, test first |

## Finishing and production

| Tool | Use | License |
|---|---|---|
| [vtracer](https://github.com/visioncortex/vtracer) | clean 2D images to real SVG vectors: rig-ready, removes stray dots | MIT |
| [IC-Light](https://github.com/lllyasviel/IC-Light) | relighting for place states (candles out, night) | V1 Apache; ⚠ V2 (FLUX) non-commercial |
| Real-ESRGAN (~65 MB) | the final upscale pass | BSD |
| LoRA training: [musubi-tuner](https://github.com/kohya-ss/musubi-tuner), [FLUX.2 klein training](https://docs.bfl.ml/flux_2/flux2_klein_training), [HF guide](https://huggingface.co/blog/black-forest-labs/flux-2-klein-lora) | a model per character or per project | official guidance 12–16 GB+ for klein 4B; 8 GB is below it (rented GPU or heavy memory tricks); building the dataset now is still useful |

## Suggested test order

1. Measured checks: rtmlib, imagehash, DINOv2 (CPU, little disk).
2. TripoSR object views (bow, lasso, Rakhsh).
3. Qwen-Image ControlNet Union with mannequin skeletons and place depth maps (disk permitting).
4. SEVA for place views.
5. The FLUX.2 klein prompt-length test (100 / 150 / 200 words).
