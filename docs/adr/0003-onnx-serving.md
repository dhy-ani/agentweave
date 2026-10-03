# 0003. Serve models with ONNX Runtime, not PyTorch

Status: Accepted

## Context
The serving process loaded PyTorch, transformers, PEFT and ultralytics. Resident memory was about 1.1 GB, cold starts were slow, and the dependency set is far larger than Vercel's 500 MB Python function limit ([Vercel Functions limits](https://vercel.com/docs/functions/limitations)). An earlier memory fix applied PyTorch dynamic int8 quantization; parity testing later showed it had badly damaged text embeddings (cosine 0.29 minimum, 0.52 mean against fp32).

## Decision
Export the LoRA-merged CLIP vision and text towers and YOLOv8n-pose to ONNX and run them with ONNX Runtime, numpy and the `tokenizers` library. Quantize with weight-only block quantization (int8 matrices, int4 token-embedding table) because plain dynamic int8 quantization also degraded the text encoder. Gate the export with a parity script against PyTorch fp32. Replace FAISS with a numpy matrix multiply. Version model files in a manifest with SHA-256 hashes and publish them as release assets.

## Consequences
- Parity: image cosine 0.998 mean, text 0.994 mean; P@5 0.494 and mAP@5 0.459 versus 0.494 / 0.450 for PyTorch fp32; body-shape labels agree on 99.5% of images ([onnx_parity.md](../../backend/ai/data/eval/onnx_parity.md)).
- Bundle about 398 MB with models; about 385 MB resident with all models loaded; torch is never imported while serving (`/health` reports this).
- On this development machine, ONNX int8 image embedding measured slower (209 ms) than PyTorch fp32 (83 ms) when both shared one process; latency on Vercel hardware still needs measuring.
- Training and export keep a separate PyTorch environment (`requirements-train.txt`).
