"""
Singleton model cache — single OpenCLIP model for both text and image embeddings.
Using one model instead of two halves memory usage (~350MB vs ~700MB).
"""
import torch
import open_clip as oc
import numpy as np

device = "cuda" if torch.cuda.is_available() else "cpu"

_model = None
_preprocess = None
_tokenizer = None


def _load():
    global _model, _preprocess, _tokenizer
    if _model is None:
        _model, _, _preprocess = oc.create_model_and_transforms(
            "ViT-B-32", pretrained="laion400m_e32", device=device
        )
        _model.eval()
        _tokenizer = oc.get_tokenizer("ViT-B-32")
    return _model, _preprocess, _tokenizer


def get_image_model():
    m, p, _ = _load()
    return m, p


def get_text_model():
    m, _, _ = _load()
    return m


def embed_text(prompt: str) -> np.ndarray:
    model, _, tokenizer = _load()
    tokens = tokenizer([prompt]).to(device)
    with torch.no_grad():
        feats = model.encode_text(tokens)
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_image(image) -> np.ndarray:
    model, preprocess, _ = _load()
    inp = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        feats = model.encode_image(inp)
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_text_ensemble(prompts: list) -> np.ndarray:
    vecs = [embed_text(p) for p in prompts]
    avg = np.mean(vecs, axis=0).astype("float32")
    avg /= np.linalg.norm(avg)
    return avg
