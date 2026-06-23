"""
Singleton model cache — load CLIP once at startup, reuse everywhere.
"""
import torch
import clip
import open_clip as oc

device = "cuda" if torch.cuda.is_available() else "cpu"

_clip_model = None
_clip_preprocess = None
_text_model = None
_text_tokenizer = None


def get_image_model():
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        _clip_model, _, _clip_preprocess = oc.create_model_and_transforms(
            "ViT-B-32", pretrained="laion400m_e32", device=device
        )
        _clip_model.eval()
    return _clip_model, _clip_preprocess


def get_text_model():
    global _text_model, _text_tokenizer
    if _text_model is None:
        _text_model, _ = clip.load("ViT-B/32", device=device)
        _text_model.eval()
    return _text_model


def embed_text(prompt: str):
    """Return a normalised float32 numpy vector for a text prompt."""
    import numpy as np
    model = get_text_model()
    tokens = clip.tokenize([prompt]).to(device)
    with torch.no_grad():
        feats = model.encode_text(tokens)
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_image(image):
    """Return a normalised float32 numpy vector for a PIL Image."""
    import numpy as np
    model, preprocess = get_image_model()
    inp = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        feats = model.encode_image(inp)
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy().flatten().astype("float32")


def embed_text_ensemble(prompts: list):
    """Average embeddings of multiple prompts for richer query coverage."""
    import numpy as np
    vecs = [embed_text(p) for p in prompts]
    avg = np.mean(vecs, axis=0).astype("float32")
    avg /= np.linalg.norm(avg)
    return avg
