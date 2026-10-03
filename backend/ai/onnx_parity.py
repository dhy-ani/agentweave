"""
Parity check: ONNX serving path vs. the PyTorch reference (training env).

Compares, over the 205 curated images and the 25 category prompts:
  - cosine(ONNX int8, torch fp32) for image and text embeddings (plus the
    fp32 ONNX export, and the previous torch dynamic-int8 serving model, as
    reference points);
  - top-10 retrieval overlap (text -> corpus and image -> corpus) when both
    the query and the corpus come from the same backend;
  - P@5 / mAP@5 on the val split (same protocol as evaluate_retrieval.py);
  - YOLOv8n-pose keypoints, ONNX vs. ultralytics, on images with a person,
    and whether the derived body-shape label agrees.

Usage (from backend/):  python ai/onnx_parity.py
Writes ai/data/eval/onnx_parity.md
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "..", "datasets"))

from category_labels import LABEL_TO_PROMPT  # noqa: E402

from ai import artifacts  # noqa: E402
from ai.body_shape_classifier import _ultralytics_keypoints, classify_body_shape  # noqa: E402
from ai.clip_torch import as_tensor, load_merged_model  # noqa: E402
from ai.data_split import PROCESSED_DIR, get_splits, load_manifest  # noqa: E402
from ai.evaluate_retrieval import precision_and_ap_at_k  # noqa: E402
from ai.onnx_inference import ClipOnnx, PoseOnnx, preprocess_clip_image  # noqa: E402

REPORT = os.path.join(BACKEND_DIR, "ai", "data", "eval", "onnx_parity.md")
FP32_DIR = os.path.join(artifacts.DEFAULT_MODEL_DIR, "fp32")
K = 10


def _norm(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def _cos_stats(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    cos = (_norm(a) * _norm(b)).sum(axis=1)
    return float(cos.min()), float(cos.mean())


def _topk_overlap(q_a, c_a, q_b, c_b, k=K, exclude_self=False) -> float:
    sims_a, sims_b = q_a @ c_a.T, q_b @ c_b.T
    if exclude_self:
        np.fill_diagonal(sims_a, -np.inf)
        np.fill_diagonal(sims_b, -np.inf)
    top_a = np.argsort(-sims_a, axis=1)[:, :k]
    top_b = np.argsort(-sims_b, axis=1)[:, :k]
    return float(np.mean([len(set(x) & set(y)) / k for x, y in zip(top_a, top_b)]))


def torch_embeddings(model, processor, images, prompts):
    img_vecs = []
    with torch.no_grad():
        for img in images:
            pv = processor(images=img, return_tensors="pt")["pixel_values"]
            img_vecs.append(as_tensor(model.get_image_features(pixel_values=pv)).numpy()[0])
        tok = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
        txt = as_tensor(model.get_text_features(**tok)).numpy()
    return _norm(np.array(img_vecs, dtype=np.float32)), _norm(txt.astype(np.float32))


def onnx_fp32_embeddings(clip: ClipOnnx, images, prompts):
    vision = ort.InferenceSession(os.path.join(FP32_DIR, "clip_vision.onnx"))
    text = ort.InferenceSession(os.path.join(FP32_DIR, "clip_text.onnx"))
    img = np.concatenate([
        vision.run(None, {"pixel_values": preprocess_clip_image(im)[None]})[0] for im in images
    ])
    ids, mask = clip.tokenize(prompts)
    txt = text.run(None, {"input_ids": ids, "attention_mask": mask})[0]
    return _norm(img), _norm(txt)


def retrieval_metrics(vectors, labels, val_idx) -> dict:
    sim = vectors @ vectors.T
    p5, map5 = precision_and_ap_at_k(sim, labels, val_idx, 5)
    return {"p5": p5, "map5": map5}


def yolo_parity(images: list[tuple[str, Image.Image]], pose: PoseOnnx):
    rows = []
    for name, img in images:
        ref = _ultralytics_keypoints(img)
        if not ref:
            continue
        ours = pose.keypoints(img)
        if ours is None:
            rows.append((name, None, None, classify_body_shape(ref), None))
            continue
        err = np.abs(np.array(ours) - np.array(ref))
        rows.append((name, float(err.mean()), float(err.max()), classify_body_shape(ref),
                     classify_body_shape(ours)))
    return rows


def main() -> None:
    manifest = load_manifest()
    filenames = [r["filename"] for r in manifest]
    labels = [r["verified_label"] for r in manifest]
    images = [Image.open(os.path.join(PROCESSED_DIR, f)).convert("RGB") for f in filenames]
    prompts = list(LABEL_TO_PROMPT.values())
    _, val_files, _ = get_splits()
    val_idx = [filenames.index(f) for f in val_files]

    model, processor, lora = load_merged_model()
    t0 = time.perf_counter()
    ref_img, ref_txt = torch_embeddings(model, processor, images, prompts)
    t_torch = (time.perf_counter() - t0) / len(images)

    qmodel = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
    old_img, old_txt = torch_embeddings(qmodel, processor, images, prompts)
    del qmodel

    clip = ClipOnnx()
    fp_img, fp_txt = onnx_fp32_embeddings(clip, images, prompts)
    clip.embed_images(images[:1])  # warm-up so session creation isn't timed
    t0 = time.perf_counter()
    q_img = np.concatenate([clip.embed_images([im]) for im in images])
    t_onnx = (time.perf_counter() - t0) / len(images)
    q_txt = clip.embed_texts(prompts)

    variants = {"torch fp32 (reference)": (ref_img, ref_txt),
                "torch dynamic int8 (previous serving)": (old_img, old_txt),
                "ONNX fp32": (fp_img, fp_txt),
                "ONNX int8 (serving)": (q_img, q_txt)}

    lines = ["# ONNX serving parity report\n",
             f"LoRA merged into exported weights: **{lora}**. Reference = PyTorch fp32 "
             "(base CLIP + merged LoRA). Model files: "
             + ", ".join(f"`{n}` {m['size'] / 1e6:.1f} MB" for n, m in artifacts.load_manifest()["files"].items())
             + ".\n",
             f"{len(images)} curated images, {len(prompts)} text prompts (category prompts), "
             f"{len(val_idx)} val-split queries.\n",
             "## Embedding cosine similarity vs. torch fp32\n",
             "| backend | image min | image mean | text min | text mean |",
             "|---|---|---|---|---|"]
    for name, (img, txt) in variants.items():
        if name.startswith("torch fp32"):
            continue
        imin, imean = _cos_stats(img, ref_img)
        tmin, tmean = _cos_stats(txt, ref_txt)
        lines.append(f"| {name} | {imin:.4f} | {imean:.4f} | {tmin:.4f} | {tmean:.4f} |")

    lines += ["\n## Top-10 retrieval overlap with torch fp32\n",
              "Each backend embeds both the query and the 205-image corpus (as in serving).\n",
              "| backend | text->image overlap@10 | image->image overlap@10 |", "|---|---|---|"]
    for name, (img, txt) in variants.items():
        if name.startswith("torch fp32"):
            continue
        t_ov = _topk_overlap(ref_txt, ref_img, txt, img)
        i_ov = _topk_overlap(ref_img, ref_img, img, img, exclude_self=True)
        lines.append(f"| {name} | {t_ov:.3f} | {i_ov:.3f} |")

    lines += ["\n## Retrieval quality on the val split (same protocol as evaluate_retrieval.py)\n",
              "| embeddings | P@5 | mAP@5 |", "|---|---|---|"]
    cache = os.path.join(BACKEND_DIR, "ai", "data", "embedding_cache_lora.npz")
    if os.path.exists(cache):
        cached = np.load(cache, allow_pickle=True)
        if list(cached["filenames"]) == filenames:
            m = retrieval_metrics(_norm(cached["vectors"]), labels, val_idx)
            lines.append(f"| torch LoRA, ablation-report cache | {m['p5']:.3f} | {m['map5']:.3f} |")
    for name, (img, _) in variants.items():
        m = retrieval_metrics(img, labels, val_idx)
        lines.append(f"| {name} | {m['p5']:.3f} | {m['map5']:.3f} |")

    lines += ["\n## Latency (this machine, CPU, batch 1, includes preprocessing)\n",
              "Indicative only: torch and ONNX Runtime thread pools share this process here. "
              "The serving process never loads torch.\n",
              f"- torch fp32 image embedding: {t_torch * 1000:.0f} ms/image",
              f"- ONNX int8 image embedding: {t_onnx * 1000:.0f} ms/image"]

    rows = yolo_parity(list(zip(filenames, images)), PoseOnnx())
    matched = [r for r in rows if r[1] is not None]
    lines += ["\n## YOLOv8n-pose: ONNX (numpy pre/post-processing) vs. ultralytics\n",
              f"Images where ultralytics detects a person: {len(rows)} / {len(images)}; "
              f"ONNX also detects one in {len(matched)}.\n"]
    if matched:
        mean_err = np.mean([r[1] for r in matched])
        p95 = np.percentile([r[2] for r in matched], 95)
        agree = np.mean([r[3] == r[4] for r in matched])
        lines += [f"- Mean |keypoint error| (normalised xyn units, 17 keypoints): **{mean_err:.4f}** "
                  f"(~{mean_err * 100:.2f}% of image size)",
                  f"- 95th percentile of per-image max error: {p95:.4f}",
                  f"- Body-shape label agreement: **{agree:.1%}**",
                  "\nDifferences come from ultralytics' rectangular (stride-32) letterbox and "
                  "OpenCV resize vs. the fixed 640x640 PIL letterbox used by the ONNX path; "
                  "the largest errors are on low-confidence (occluded) keypoints.\n",
                  "| image | mean err | max err | ultralytics shape | onnx shape |", "|---|---|---|---|---|"]
        for r in matched[:10]:
            lines.append(f"| {r[0]} | {r[1]:.4f} | {r[2]:.4f} | {r[3]} | {r[4]} |")

    report = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
