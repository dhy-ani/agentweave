# ONNX serving parity report

LoRA merged into exported weights: **True**. Reference = PyTorch fp32 (base CLIP + merged LoRA). Model files: `clip_vision_int8.onnx` 98.4 MB, `clip_text_int8.onnx` 55.7 MB, `yolov8n_pose.onnx` 13.5 MB.

205 curated images, 26 text prompts (category prompts), 32 val-split queries.

## Embedding cosine similarity vs. torch fp32

| backend | image min | image mean | text min | text mean |
|---|---|---|---|---|
| torch dynamic int8 (previous serving) | 0.8542 | 0.9308 | 0.2864 | 0.5155 |
| ONNX fp32 | 0.9999 | 1.0000 | 1.0000 | 1.0000 |
| ONNX int8 (serving) | 0.9750 | 0.9983 | 0.9874 | 0.9937 |

## Top-10 retrieval overlap with torch fp32

Each backend embeds both the query and the 205-image corpus (as in serving).

| backend | text->image overlap@10 | image->image overlap@10 |
|---|---|---|
| torch dynamic int8 (previous serving) | 0.523 | 0.756 |
| ONNX fp32 | 0.996 | 0.999 |
| ONNX int8 (serving) | 0.942 | 0.961 |

## Retrieval quality on the val split (same protocol as evaluate_retrieval.py)

| embeddings | P@5 | mAP@5 |
|---|---|---|
| torch LoRA, ablation-report cache | 0.494 | 0.450 |
| torch fp32 (reference) | 0.494 | 0.450 |
| torch dynamic int8 (previous serving) | 0.506 | 0.443 |
| ONNX fp32 | 0.494 | 0.450 |
| ONNX int8 (serving) | 0.494 | 0.459 |

## Latency (this machine, CPU, batch 1, includes preprocessing)

Indicative only: torch and ONNX Runtime thread pools share this process here. The serving process never loads torch.

- torch fp32 image embedding: 83 ms/image
- ONNX int8 image embedding: 209 ms/image

## YOLOv8n-pose: ONNX (numpy pre/post-processing) vs. ultralytics

Images where ultralytics detects a person: 198 / 205; ONNX also detects one in 197.

- Mean |keypoint error| (normalised xyn units, 17 keypoints): **0.0040** (~0.40% of image size)
- 95th percentile of per-image max error: 0.0878
- Body-shape label agreement: **99.5%**

Differences come from ultralytics' rectangular (stride-32) letterbox and OpenCV resize vs. the fixed 640x640 PIL letterbox used by the ONNX path; the largest errors are on low-confidence (occluded) keypoints.

| image | mean err | max err | ultralytics shape | onnx shape |
|---|---|---|---|---|
| Korean_str_0.jpg | 0.0004 | 0.0015 | inverted_triangle | inverted_triangle |
| Korean_str_1.jpg | 0.0015 | 0.0051 | inverted_triangle | inverted_triangle |
| Korean_str_2.jpg | 0.0009 | 0.0060 | inverted_triangle | inverted_triangle |
| Korean_str_3.jpg | 0.0012 | 0.0035 | inverted_triangle | inverted_triangle |
| Korean_str_4.jpg | 0.0038 | 0.0143 | inverted_triangle | inverted_triangle |
| Korean_str_5.jpg | 0.0012 | 0.0068 | inverted_triangle | inverted_triangle |
| Y2K_pastel_0.jpg | 0.0003 | 0.0012 | inverted_triangle | inverted_triangle |
| Y2K_pastel_1.jpg | 0.0004 | 0.0019 | inverted_triangle | inverted_triangle |
| Y2K_pastel_2.jpg | 0.0109 | 0.0356 | inverted_triangle | inverted_triangle |
| Y2K_pastel_3.jpg | 0.0162 | 0.1177 | inverted_triangle | inverted_triangle |
