"""
Singleton model cache — a single CLIP model (HuggingFace `transformers`) used
for both text and image embeddings, with an optional LoRA adapter fine-tuned
on the curated AgentWeave fashion dataset (see ai/finetune_clip_lora.py).

Switched from `open_clip_torch`'s ViT-B-32/laion400m_e32 to the HuggingFace
equivalent LAION checkpoint `laion/CLIP-ViT-B-32-laion2B-s34B-b79K` (same
lineage, same 512-d output space) because `transformers` + `peft` is the
standard, well-supported path to LoRA-fine-tuning CLIP -- `open_clip` doesn't
have first-class PEFT integration.

If a trained LoRA adapter exists under ai/data/lora_adapter/, it is loaded
and merged into the base weights at startup. If it's missing (fresh
checkout, or mid-training), embed_* silently falls back to the raw zero-shot
base-model embeddings -- the live API must never break just because the
adapter hasn't been trained/copied yet.
"""
import os
import torch
import numpy as np

device = "cuda" if torch.cuda.is_available() else "cpu"

CHECKPOINT = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
ADAPTER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "lora_adapter")

_model = None
_processor = None
_using_lora = False


def _load():
    global _model, _processor, _using_lora
    if _model is not None:
        return _model, _processor

    from transformers import CLIPModel, CLIPProcessor

    base_model = CLIPModel.from_pretrained(CHECKPOINT)
    _processor = CLIPProcessor.from_pretrained(CHECKPOINT)

    has_adapter = os.path.isdir(ADAPTER_DIR) and os.path.exists(
        os.path.join(ADAPTER_DIR, "adapter_config.json")
    )
    if has_adapter:
        try:
            from peft import PeftModel

            adapted = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
            base_model = adapted.merge_and_unload()  # bake LoRA deltas in for plain, fast inference
            _using_lora = True
            print(f"[model_cache] loaded LoRA adapter from {ADAPTER_DIR}")
        except Exception as e:
            print(f"[model_cache] WARNING: failed to load LoRA adapter ({e}); "
                  f"falling back to base CLIP embeddings")
            _using_lora = False
    else:
        print("[model_cache] no LoRA adapter found at "
              f"{ADAPTER_DIR} -- using zero-shot base CLIP embeddings")
        _using_lora = False

    base_model.to(device)
    base_model.eval()

    # Dynamic int8 quantization of the Linear layers -- these are ~all of a
    # ViT's parameter count (attention + MLP projections), so this cuts the
    # model's resident memory roughly 3-4x on CPU with negligible accuracy
    # loss (weights-only quantization, activations stay fp32). This is what
    # makes it feasible to run on a memory-capped host (e.g. Render's free/
    # low tiers) instead of requiring a much larger instance. CPU-only --
    # quantized int8 kernels aren't the CUDA path, so skip on GPU.
    if device == "cpu" and os.environ.get("AGENTWEAVE_NO_QUANTIZE") != "1":
        import gc
        import torch.nn as nn
        fp32_model = base_model
        base_model = torch.quantization.quantize_dynamic(
            fp32_model, {nn.Linear}, dtype=torch.qint8
        )
        # quantize_dynamic() copies rather than mutates in place, so the fp32
        # source briefly coexists with the new int8 model -- drop it and force
        # a collection so that transient peak gets reclaimed by the allocator
        # instead of sitting in the process's resident set indefinitely.
        del fp32_model
        gc.collect()

    _model = base_model
    return _model, _processor


def is_lora_active() -> bool:
    """True once a trained LoRA adapter has actually been loaded and merged."""
    _load()
    return _using_lora


def get_image_model():
    m, p = _load()
    return m, p


def get_text_model():
    m, _ = _load()
    return m


def _as_tensor(features):
    """transformers>=4.5x's CLIPModel.get_{text,image}_features returns a plain
    projected tensor on some versions and a BaseModelOutputWithPooling (with
    the projected features stashed in .pooler_output) on others. Normalize."""
    if torch.is_tensor(features):
        return features
    return features.pooler_output


def embed_text(prompt: str) -> np.ndarray:
    model, processor = _load()
    inputs = processor(text=[prompt], return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_text_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_image(image) -> np.ndarray:
    model, processor = _load()
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        feats = _as_tensor(model.get_image_features(**inputs))
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_text_ensemble(prompts: list) -> np.ndarray:
    vecs = [embed_text(p) for p in prompts]
    avg = np.mean(vecs, axis=0).astype("float32")
    avg /= np.linalg.norm(avg)
    return avg
