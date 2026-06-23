from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import sys
import faiss
import numpy as np
import json
from datetime import datetime
import random
from PIL import Image
import io

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ai.model_cache import embed_text, embed_text_ensemble, embed_image

router = APIRouter(prefix="/stylegenie", tags=["StyleGenie"])

# ── Pydantic models ──────────────────────────────────────────────────────────

class StyleRequest(BaseModel):
    weather: str
    occasion: str
    location: str
    occupation: str
    relevance: Optional[str] = "current"

class TrendPrompt(BaseModel):
    prompt: str
    gender: Optional[str] = ""
    body_type: Optional[str] = ""
    weather: Optional[str] = ""
    occasion: Optional[str] = ""

# ── Load FAISS index & metadata once at import time ──────────────────────────

_base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

try:
    faiss_index = faiss.read_index(os.path.join(_base, "ai/data/trends.index"))
    with open(os.path.join(_base, "ai/data/index_to_caption.json")) as f:
        index_to_caption = json.load(f)
    with open(os.path.join(_base, "ai/data/index_to_image_path.json")) as f:
        index_to_image_path = json.load(f)
    with open(os.path.join(_base, "ai/data/index_to_timestamp.json")) as f:
        index_to_timestamp = json.load(f)
except Exception as e:
    raise RuntimeError(f"Failed to load FAISS index or metadata: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _trendiness(days_old: float, scale: float = 30.0) -> float:
    return round(100.0 * float(np.exp(-days_old / scale)), 1)


def _mmr_rerank(query_vec: np.ndarray, indices: list, vectors: np.ndarray,
                top_k: int = 10, lambda_: float = 0.6) -> list:
    """
    Max Marginal Relevance: balance relevance vs. diversity.
    lambda_ = 1 → pure relevance; 0 → pure diversity.
    """
    selected, remaining = [], list(indices)

    while remaining and len(selected) < top_k:
        best_idx, best_score = None, -np.inf
        for idx in remaining:
            rel = float(np.dot(query_vec, vectors[idx]))
            if selected:
                red = max(float(np.dot(vectors[idx], vectors[s])) for s in selected)
            else:
                red = 0.0
            score = lambda_ * rel - (1 - lambda_) * red
            if score > best_score:
                best_score, best_idx = score, idx
        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected


def _build_result(idx: int, distance: float) -> dict:
    idx_s = str(idx)
    filename = os.path.basename(index_to_image_path.get(idx_s, ""))
    caption = index_to_caption.get(idx_s, "Outfit")
    ts_raw = index_to_timestamp.get(idx_s)
    days_old = (datetime.now() - datetime.fromisoformat(ts_raw)).days if ts_raw else 60
    trend_score = _trendiness(days_old)
    projection = (
        random.choice([
            "This trend is exploding this season.",
            "This style is rapidly gaining popularity.",
            "A top pick for the current fashion cycle.",
        ]) if trend_score > 60 else
        "This trend is fading — try something fresher soon!"
    )
    return {
        "result": f"Trending look: {caption}",
        "image": filename,
        "trendiness_score": trend_score,
        "future_projection": projection,
        "source": "trend-vector",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/trend_vector")
async def recommend_outfit(data: TrendPrompt):
    try:
        # Build an ensemble of query prompts for broader coverage
        base = data.prompt
        expansions = [base]
        if data.gender:
            expansions.append(f"{data.gender} fashion outfit {data.occasion or ''} {data.weather or ''}".strip())
        if data.body_type:
            expansions.append(f"flattering outfit for {data.body_type} body shape {data.occasion or ''}".strip())

        query_vec = embed_text_ensemble(expansions).reshape(1, -1)

        # Retrieve more candidates so MMR has room to diversify
        k_retrieve = min(30, faiss_index.ntotal)
        D, I = faiss_index.search(query_vec, k=k_retrieve)

        raw_indices = [int(i) for i in I[0] if i >= 0]
        if not raw_indices:
            raise HTTPException(status_code=404, detail="No results found.")

        # Load stored vectors for MMR (reuse the numpy matrix from the FAISS index)
        stored = np.array([faiss_index.reconstruct(i) for i in raw_indices]).astype("float32")
        q_flat = query_vec.flatten().astype("float32")
        reranked = _mmr_rerank(q_flat, list(range(len(raw_indices))), stored, top_k=10)

        results = [_build_result(raw_indices[r], float(D[0][r])) for r in reranked]
        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trend vector search failed: {str(e)}")


@router.post("/image_search")
async def search_by_image(file: UploadFile = File(...)):
    """Find trend-similar outfits by uploading a reference image."""
    try:
        img = Image.open(io.BytesIO(await file.read())).convert("RGB")
        query_vec = embed_image(img).reshape(1, -1)

        k_retrieve = min(20, faiss_index.ntotal)
        D, I = faiss_index.search(query_vec, k=k_retrieve)
        raw_indices = [int(i) for i in I[0] if i >= 0]

        results = [_build_result(raw_indices[r], float(D[0][r])) for r in range(min(10, len(raw_indices)))]
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image search failed: {str(e)}")
