"""
Export the serving models to ONNX (training-environment script; needs torch,
transformers, peft, ultralytics, onnx, onnxruntime).

  1. CLIP (base laion checkpoint + merged LoRA adapter, exactly as
     ai/clip_torch.py loads it) split into two graphs:
       clip_vision: pixel_values[B,3,224,224]            -> image_embeds[B,512]
       clip_text:   input_ids[B,T], attention_mask[B,T]  -> text_embeds[B,512]
     Outputs are the raw projected embeddings; L2 normalisation happens in
     numpy at inference time. Both get block-wise weight-only quantization
     (int8 MatMul weights, int4 token embeddings; see _quantize).
  2. YOLOv8n-pose -> yolov8n_pose.onnx (static 1x3x640x640, fp32; 13 MB).

Outputs land in backend/ai/models/ (gitignored); fp32 CLIP graphs are kept
under models/fp32/ for the parity check and are never deployed. Afterwards
the manifest (names, sizes, sha256) is rewritten so ai/artifacts.py can
verify downloads.

Usage (from backend/):
    python ai/export_onnx.py              # export everything
    python ai/export_onnx.py --skip-yolo
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys

import torch

AI_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(AI_DIR)
sys.path.insert(0, BACKEND_DIR)

from ai import artifacts  # noqa: E402
from ai.clip_torch import CHECKPOINT, load_merged_model  # noqa: E402

MODELS_DIR = artifacts.DEFAULT_MODEL_DIR
FP32_DIR = os.path.join(MODELS_DIR, "fp32")
YOLO_WEIGHTS = os.path.join(BACKEND_DIR, "yolov8n-pose.pt")
OPSET = 17


class _VisionTower(torch.nn.Module):
    def __init__(self, clip):
        super().__init__()
        self.vision_model = clip.vision_model
        self.visual_projection = clip.visual_projection

    def forward(self, pixel_values):
        pooled = self.vision_model(pixel_values=pixel_values).pooler_output
        return self.visual_projection(pooled)


class _TextTower(torch.nn.Module):
    def __init__(self, clip):
        super().__init__()
        self.text_model = clip.text_model
        self.text_projection = clip.text_projection

    def forward(self, input_ids, attention_mask):
        pooled = self.text_model(input_ids=input_ids, attention_mask=attention_mask).pooler_output
        return self.text_projection(pooled)


def _export(module: torch.nn.Module, args: tuple, path: str, input_names: list[str],
            output_name: str, dynamic_axes: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(
            module, args, path,
            input_names=input_names,
            output_names=[output_name],
            dynamic_axes=dynamic_axes,
            opset_version=OPSET,
            do_constant_folding=True,
            dynamo=False,
        )


def _weight_only(model, *, bits: int, block_size: int, op_type: str, accuracy_level: int | None = None,
                 nodes_to_include: list[str] | None = None):
    import onnx
    from onnxruntime.quantization.matmul_nbits_quantizer import (
        DefaultWeightOnlyQuantConfig,
        MatMulNBitsQuantizer,
    )

    axis = 1 if op_type == "Gather" else 0
    config = DefaultWeightOnlyQuantConfig(
        block_size=block_size, is_symmetric=True, bits=bits, accuracy_level=accuracy_level,
        op_types_to_quantize=(op_type,), quant_axes=((op_type, axis),),
    )
    quantizer = MatMulNBitsQuantizer(
        model if isinstance(model, onnx.ModelProto) else onnx.load(model),
        nodes_to_include=nodes_to_include, algo_config=config,
    )
    quantizer.process()
    return quantizer.model.model


def _quantize(src: str, dst: str) -> None:
    """Weight-only block quantization (activations stay fp32).

    Plain `quantize_dynamic` (per-tensor uint8 activations) collapses the text
    tower (cosine vs fp32 down to ~0.65) because of the large activation
    outliers entering each mlp.fc2. Block-wise weight-only quantization avoids
    that: MatMul weights -> int8 (block 128, accuracy_level 4 = int8 compute
    per block), and the 49408x512 token-embedding table -> int4 (block 32),
    which is both smaller and more accurate than per-tensor int8 for it.
    """
    import onnx
    from onnxruntime.quantization.shape_inference import quant_pre_process

    prepped = src.replace(".onnx", ".prep.onnx")
    quant_pre_process(src, prepped, skip_symbolic_shape=True)
    model = onnx.load(prepped)
    os.remove(prepped)

    token_gathers = [
        node.name for node in model.graph.node
        if node.op_type == "Gather" and "token_embedding" in node.input[0]
    ]
    if token_gathers:
        model = _weight_only(model, bits=4, block_size=32, op_type="Gather", nodes_to_include=token_gathers)
    model = _weight_only(model, bits=8, block_size=128, op_type="MatMul", accuracy_level=4)
    onnx.save_model(model, dst)


def export_clip() -> bool:
    """Export + quantize both CLIP towers; returns whether a LoRA adapter was merged."""
    clip, _, lora = load_merged_model()
    clip = clip.float().eval()
    print(f"LoRA merged: {lora}")

    vision_fp32 = os.path.join(FP32_DIR, "clip_vision.onnx")
    text_fp32 = os.path.join(FP32_DIR, "clip_text.onnx")

    _export(_VisionTower(clip), (torch.randn(1, 3, 224, 224),), vision_fp32,
            ["pixel_values"], "image_embeds", {"pixel_values": {0: "batch"}, "image_embeds": {0: "batch"}})

    ids = torch.tensor([[49406, 320, 1125, 49407]], dtype=torch.long)
    _export(_TextTower(clip), (ids, torch.ones_like(ids)), text_fp32,
            ["input_ids", "attention_mask"], "text_embeds",
            {"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"},
             "text_embeds": {0: "batch"}})

    _quantize(vision_fp32, os.path.join(MODELS_DIR, "clip_vision_int8.onnx"))
    _quantize(text_fp32, os.path.join(MODELS_DIR, "clip_text_int8.onnx"))
    return lora


def export_yolo() -> None:
    from ultralytics import YOLO

    out = YOLO(YOLO_WEIGHTS).export(format="onnx", imgsz=640, opset=OPSET, dynamic=False,
                                    simplify=False, half=False)
    shutil.move(out, os.path.join(MODELS_DIR, "yolov8n_pose.onnx"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-clip", action="store_true")
    parser.add_argument("--skip-yolo", action="store_true")
    opts = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("onnxruntime.quantization.matmul_nbits_quantizer").setLevel(logging.WARNING)

    os.makedirs(MODELS_DIR, exist_ok=True)
    metadata = {}
    if not opts.skip_clip:
        metadata = {"checkpoint": CHECKPOINT, "lora_merged": export_clip()}
    if not opts.skip_yolo:
        export_yolo()

    manifest = artifacts.write_manifest(MODELS_DIR, **metadata)
    for name, meta in manifest["files"].items():
        print(f"{name:28s} {meta['size'] / 1e6:8.1f} MB  sha256={meta['sha256'][:12]}...")


if __name__ == "__main__":
    main()
