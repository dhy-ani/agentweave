"""
PyTorch CLIP backend (training / evaluation / ONNX export only).

Loads `laion/CLIP-ViT-B-32-laion2B-s34B-b79K` via HF `transformers` and, if a
trained LoRA adapter exists under ai/data/lora_adapter/, merges it into the
base weights. The live API does not import this module: it serves the ONNX
export of the same merged model (see ai/export_onnx.py, ai/onnx_inference.py).
Select it explicitly with AGENTWEAVE_BACKEND=torch.
"""
from __future__ import annotations

import gc
import logging
import os

import numpy as np
import torch

logger = logging.getLogger(__name__)

CHECKPOINT = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
ADAPTER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "lora_adapter")

device = "cuda" if torch.cuda.is_available() else "cpu"

_model = None
_processor = None
_using_lora = False


def load_merged_model(with_lora: bool = True):
    """Return (fp32 CLIPModel with LoRA merged if available, CLIPProcessor, lora_applied)."""
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(CHECKPOINT)
    processor = CLIPProcessor.from_pretrained(CHECKPOINT)
    applied = False

    has_adapter = os.path.exists(os.path.join(ADAPTER_DIR, "adapter_config.json"))
    if with_lora and has_adapter:
        try:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, ADAPTER_DIR).merge_and_unload()
            applied = True
            logger.info("Loaded LoRA adapter from %s", ADAPTER_DIR)
        except Exception as exc:  # the API must keep working without the adapter
            logger.warning("Failed to load LoRA adapter (%s); using base CLIP", exc)
    elif with_lora:
        logger.info("No LoRA adapter at %s; using zero-shot base CLIP", ADAPTER_DIR)

    model.eval()
    return model, processor, applied


def _load():
    global _model, _processor, _using_lora
    if _model is not None:
        return _model, _processor

    model, _processor, _using_lora = load_merged_model()
    model.to(device)

    # Weights-only int8 quantization of the Linear layers cuts resident memory
    # roughly 3-4x on CPU; CUDA has no quantized kernels for this path.
    if device == "cpu" and os.environ.get("AGENTWEAVE_NO_QUANTIZE") != "1":
        fp32_model = model
        model = torch.quantization.quantize_dynamic(fp32_model, {torch.nn.Linear}, dtype=torch.qint8)
        # quantize_dynamic copies, so release the fp32 original explicitly.
        del fp32_model
        gc.collect()

    _model = model
    return _model, _processor


def as_tensor(features) -> torch.Tensor:
    """get_{text,image}_features returns a tensor on some transformers versions
    and a BaseModelOutputWithPooling (projected features in pooler_output) on others."""
    if torch.is_tensor(features):
        return features
    return features.pooler_output


def is_lora_active() -> bool:
    _load()
    return _using_lora


def is_loaded() -> bool:
    return _model is not None


def embed_text(prompt: str) -> np.ndarray:
    return embed_texts([prompt])[0]


def embed_texts(prompts: list[str]) -> np.ndarray:
    model, processor = _load()
    inputs = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = as_tensor(model.get_text_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().astype("float32")


def embed_image(image) -> np.ndarray:
    model, processor = _load()
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = as_tensor(model.get_image_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")
