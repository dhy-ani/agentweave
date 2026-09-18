from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import sys
import faiss
import numpy as np
import json
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
except Exception as e:
    raise RuntimeError(f"Failed to load FAISS index or metadata: {e}")

# index -> cluster_id (from ai/cluster_images.py, keyed the same way as the
# FAISS index -- see ai/data_split.py / generate_faiss_data.py, both of which
# iterate datasets/curated_manifest.csv in the same row order). Used for the
# "% of collection sharing this cluster" secondary signal below. Optional:
# the app must still work before tune_clustering.py/cluster_images.py have
# ever been run.
_index_to_cluster = {}
_cluster_share_pct = {}
try:
    with open(os.path.join(_base, "ai/data/index_to_cluster.json")) as f:
        _index_to_cluster = json.load(f)
    _cluster_counts = {}
    for cid in _index_to_cluster.values():
        _cluster_counts[cid] = _cluster_counts.get(cid, 0) + 1
    _total_clustered = len(_index_to_cluster)
    _cluster_share_pct = {cid: round(100.0 * n / _total_clustered, 1) for cid, n in _cluster_counts.items()}
except FileNotFoundError:
    pass  # clustering hasn't been run yet -- cluster-share signal simply omitted


# ── Helpers ───────────────────────────────────────────────────────────────────
#
# NOTE on what used to be here: `_trendiness()` computed a fake exponential-
# decay "trend score" from ai/generate_timestamps.py's *randomly generated*
# per-image dates, and `_build_result()` picked celebratory/fading flavor
# text based on that fake score. None of it reflected anything real about
# the images. It's replaced below with signals actually computed from the
# retrieval itself:
#   1. match_score: derived from the FAISS L2 distance between the query
#      and this result. Embeddings are L2-normalized, so for unit vectors
#      ||q - v||^2 = 2 - 2*cos_sim(q, v)  =>  cos_sim = 1 - distance/2.
#      This is an honest "how close is this to what you asked for" score,
#      not a claim about real-world fashion trend velocity.
#   2. cluster_share_pct (optional): what fraction of the curated
#      collection shares this result's visual cluster (ai/cluster_images.py
#      / ai/tune_clustering.py) -- a real, precomputed statistic about the
#      dataset, not a prediction.
# ai/generate_timestamps.py is left in place (per the plan, not deleted)
# but is no longer imported or used anywhere in this live request path.

def _match_score(distance: float) -> float:
    """Convert a FAISS squared-L2 distance between two unit vectors into a
    0-100 cosine-similarity-based match-confidence score."""
    cos_sim = 1.0 - (float(distance) / 2.0)
    cos_sim = max(-1.0, min(1.0, cos_sim))
    return round(100.0 * max(0.0, cos_sim), 1)


def _match_description(match_score: float, cluster_share: float | None) -> str:
    if match_score >= 80:
        desc = "Strong match to your style search."
    elif match_score >= 60:
        desc = "Good match — reasonably close to what you asked for."
    else:
        desc = "Loose match — try narrowing your search for closer results."
    if cluster_share is not None:
        desc += f" Shares its visual cluster with {cluster_share:.0f}% of the curated collection."
    return desc


def _mmr_rerank(query_vec: np.ndarray, indices: list, vectors: np.ndarray,
                top_k: int = 10, lambda_: float = 0.7) -> list:
    """
    Max Marginal Relevance: balance relevance vs. diversity.
    lambda_ = 1 → pure relevance; 0 → pure diversity.

    lambda_=0.7 was chosen by grid-sweeping {0.3..0.9} against a proxy
    metric (mean relevance to a category-prompt query vs. label diversity
    of the top-10 results) in ai/tune_mmr_lambda.py -- see that file for
    the full method. This is a one-time offline tune, not live per-request
    tuning; re-run that script and update this default if the dataset or
    embedding model changes meaningfully.
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

    match_score = _match_score(distance)
    cluster_id = _index_to_cluster.get(idx_s)
    cluster_share = _cluster_share_pct.get(cluster_id) if cluster_id is not None else None
    description = _match_description(match_score, cluster_share)

    return {
        "result": f"Style match: {caption}",
        "image": filename,
        # Kept as `trendiness_score` for frontend compatibility (FashionCard.jsx
        # renders this as a 0-100 badge) -- the VALUE is now a real FAISS-
        # similarity-based match-confidence score, not a fabricated trend decay.
        "trendiness_score": match_score,
        "match_score": match_score,
        "cluster_share_pct": cluster_share,
        # Kept as `future_projection` for frontend compatibility (rendered as
        # the italic caption line) -- now an honest description of match
        # quality instead of randomly-chosen "trending" flavor text.
        "future_projection": description,
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
