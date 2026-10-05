"""
Exact nearest-neighbour search over the curated trend corpus in plain numpy.

The corpus is ~205 x 512 L2-normalised float32 vectors (~420 KB), so one
matrix-vector product is both exact and faster than a FAISS IndexFlatL2
round trip, and it drops faiss from the serving dependencies. Corpus vectors
come from the same ONNX model that embeds queries at serving time
(ai/build_corpus_embeddings.py), so scores are directly comparable.
"""
from __future__ import annotations

import json
import logging
import ntpath
import os
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS_FILE = os.path.join(DATA_DIR, "corpus_embeddings.npy")
CORPUS_META_FILE = os.path.join(DATA_DIR, "corpus_embeddings.meta.json")

# lambda=0.7 was picked by grid-sweeping {0.3..0.9} in ai/tune_mmr_lambda.py
# (relevance to a category prompt vs. label diversity of the top 10).
MMR_LAMBDA = 0.7


def _load_json(name: str) -> dict[str, str]:
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def image_filename(path: str) -> str:
    # index_to_image_path.json was generated on Windows; ntpath splits both / and \.
    return ntpath.basename(path)


@dataclass
class TrendCorpus:
    vectors: np.ndarray
    captions: dict[str, str]
    image_paths: dict[str, str]
    clusters: dict[str, int] = field(default_factory=dict)
    cluster_share_pct: dict[int, float] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.vectors.shape[0])

    def search(self, query: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Top-k corpus indices by cosine similarity (descending) and their similarities."""
        sims = self.vectors @ query.astype(np.float32).ravel()
        k = min(k, len(sims))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top], kind="stable")]
        return top, sims[top]

    def filename(self, idx: int) -> str:
        return image_filename(self.image_paths.get(str(idx), ""))

    def caption(self, idx: int, default: str = "Outfit") -> str:
        return self.captions.get(str(idx), default)

    def cluster_share(self, idx: int) -> float | None:
        cluster_id = self.clusters.get(str(idx))
        return self.cluster_share_pct.get(cluster_id) if cluster_id is not None else None


def mmr_rerank(query: np.ndarray, candidates: np.ndarray, top_k: int = 10,
               lambda_: float = MMR_LAMBDA) -> list[int]:
    """Max Marginal Relevance over candidate vectors (rows of `candidates`).

    Returns row indices into `candidates`. lambda_=1 is pure relevance, 0 pure diversity.
    """
    relevance = candidates @ query
    pairwise = candidates @ candidates.T
    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < top_k:
        if selected:
            redundancy = pairwise[np.ix_(remaining, selected)].max(axis=1)
        else:
            redundancy = np.zeros(len(remaining), dtype=np.float32)
        scores = lambda_ * relevance[remaining] - (1 - lambda_) * redundancy
        best = remaining[int(np.argmax(scores))]
        selected.append(best)
        remaining.remove(best)
    return selected


def match_score(cos_sim: float) -> float:
    """Cosine similarity -> 0-100 match-confidence score."""
    return round(100.0 * max(0.0, min(1.0, float(cos_sim))), 1)


@lru_cache(maxsize=1)
def get_corpus() -> TrendCorpus:
    vectors = np.load(CORPUS_FILE).astype(np.float32)
    captions = _load_json("index_to_caption.json")
    image_paths = _load_json("index_to_image_path.json")
    if len(image_paths) != len(vectors):
        raise RuntimeError(
            f"{CORPUS_FILE} has {len(vectors)} rows but index_to_image_path.json has "
            f"{len(image_paths)} entries; re-run ai/build_corpus_embeddings.py"
        )

    clusters: dict[str, int] = {}
    share: dict[int, float] = {}
    try:
        clusters = _load_json("index_to_cluster.json")
        counts: dict[int, int] = {}
        for cid in clusters.values():
            counts[cid] = counts.get(cid, 0) + 1
        share = {cid: round(100.0 * n / len(clusters), 1) for cid, n in counts.items()}
    except FileNotFoundError:
        pass  # clustering is optional; the cluster-share signal is simply omitted

    _warn_if_stale()
    logger.info("Loaded trend corpus: %d x %d", *vectors.shape)
    return TrendCorpus(vectors, captions, image_paths, clusters, share)


def _warn_if_stale() -> None:
    try:
        with open(CORPUS_META_FILE, encoding="utf-8") as f:
            built_with = json.load(f).get("clip_vision_sha256")
        from . import artifacts

        current = artifacts.load_manifest()["files"]["clip_vision_int8.onnx"]["sha256"]
    except (FileNotFoundError, KeyError):
        return
    if built_with != current:
        logger.warning("Corpus embeddings were built with a different vision model; "
                       "re-run ai/build_corpus_embeddings.py")
