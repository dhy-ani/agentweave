"""
StyleGenie retrieval endpoints: text prompt or reference image -> curated looks.

Result fields are real retrieval signals, not fabricated trend scores:
  match_score        calibrated 0-100: where the query/result cosine falls among
                     known same-aesthetic pairs for that query type
                     (ai/score_calibration.py); 50 = as close as a typical match.
  similarity         the raw cosine similarity, for transparency.
  cluster_share_pct  share of the curated collection in the result's visual
                     cluster (ai/cluster_images.py), when clustering exists.
`trendiness_score` and `future_projection` keep their names for frontend
compatibility but carry the match score and an honest description of it.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ai.model_cache import embed_image, embed_text_ensemble
from ai.retrieval import get_corpus, mmr_rerank
from ai.score_calibration import calibrated_score
from image_io import read_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stylegenie", tags=["StyleGenie"])

MMR_CANDIDATES = 30
IMAGE_SEARCH_CANDIDATES = 20
RESULTS = 10


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


def _match_description(score: float, cluster_share: float | None) -> str:
    if score >= 75:
        desc = "Strong match to your style search."
    elif score >= 40:
        desc = "Good match - reasonably close to what you asked for."
    else:
        desc = "Loose match - try narrowing your search for closer results."
    if cluster_share is not None:
        desc += f" Shares its visual cluster with {cluster_share:.0f}% of the curated collection."
    return desc


def _build_result(idx: int, cos_sim: float, modality: str = "text") -> dict:
    corpus = get_corpus()
    score = calibrated_score(cos_sim, modality)
    cluster_share = corpus.cluster_share(idx)
    return {
        "result": f"Style match: {corpus.caption(idx)}",
        "image": corpus.filename(idx),
        "trendiness_score": score,
        "match_score": score,
        "similarity": round(float(cos_sim), 4),
        "cluster_share_pct": cluster_share,
        "future_projection": _match_description(score, cluster_share),
        "source": "trend-vector",
    }


def _expand_prompt(data: TrendPrompt) -> list[str]:
    prompts = [data.prompt]
    if data.gender:
        prompts.append(f"{data.gender} fashion outfit {data.occasion or ''} {data.weather or ''}".strip())
    if data.body_type:
        prompts.append(f"flattering outfit for {data.body_type} body shape {data.occasion or ''}".strip())
    return prompts


@router.post("/trend_vector")
def recommend_outfit(data: TrendPrompt):
    try:
        corpus = get_corpus()
        query = embed_text_ensemble(_expand_prompt(data))
        # Over-retrieve so MMR has room to diversify the final top 10.
        candidates, sims = corpus.search(query, MMR_CANDIDATES)
        if len(candidates) == 0:
            raise HTTPException(status_code=404, detail="No results found.")
        order = mmr_rerank(query, corpus.vectors[candidates], top_k=RESULTS)
        return {"results": [_build_result(int(candidates[r]), float(sims[r])) for r in order]}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("trend_vector failed")
        raise HTTPException(status_code=500, detail=f"Trend vector search failed: {exc}") from exc


@router.post("/image_search")
async def search_by_image(file: UploadFile = File(...)):
    """Find curated looks similar to an uploaded reference image."""
    image = await read_image(file)
    try:
        query = await run_in_threadpool(embed_image, image)
        candidates, sims = get_corpus().search(query, IMAGE_SEARCH_CANDIDATES)
        results = [_build_result(int(i), float(s), "image") for i, s in zip(candidates[:RESULTS], sims[:RESULTS], strict=True)]
        return {"results": results}
    except Exception as exc:
        logger.exception("image_search failed")
        raise HTTPException(status_code=500, detail=f"Image search failed: {exc}") from exc
