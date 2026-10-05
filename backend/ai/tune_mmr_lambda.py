"""
Grid-sweep the MMR re-ranker's lambda_ (backend/routers/stylegenie.py's
`_mmr_rerank`, previously hardcoded to 0.6 with no justification -- Part
A5/A6 of the ML overhaul plan).

lambda_ trades off relevance (lambda_=1, pure nearest-neighbor) against
diversity (lambda_=0, actively avoids near-duplicate results). Proxy
metric, since there's no click-through data to optimize against: for each
of this dataset's 25 verified aesthetic categories, use its CLIP text
prompt as a query (mirroring how /stylegenie/trend_vector actually queries
the index), retrieve the top-30 FAISS candidates, MMR-rerank to the top 10
at each candidate lambda_, and measure:

  - relevance@10: mean cosine similarity between the query and the 10
    selected results (higher = closer to what was actually asked for)
  - diversity@10: number of *distinct* verified_labels among the 10
    selected results, divided by 10 (higher = less redundant, so a user
    doesn't see 10 near-identical outfits for one query)

Both metrics are min-max normalized across the sweep and summed into a
composite score; the lambda_ with the highest composite wins. This is a
deliberately simple, explainable proxy -- not a claim that it's the
"true" optimum, just a documented, reproducible way to pick a value
instead of asserting one.

Usage:
    python ai/tune_mmr_lambda.py
Prints the sweep table and the winning lambda_ (hardcode the result into
routers/stylegenie.py's `_mmr_rerank` default, per this file's docstring
there).
"""
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "datasets"))
os.environ.setdefault("AGENTWEAVE_BACKEND", "torch")
import model_cache
from embedding_cache import get_all_embeddings
from category_labels import LABEL_TO_PROMPT

LAMBDA_GRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
K_RETRIEVE = 30
K_FINAL = 10


def mmr_rerank(query_vec, indices, vectors, top_k, lambda_):
    selected, remaining = [], list(indices)
    while remaining and len(selected) < top_k:
        best_idx, best_score = None, -np.inf
        for idx in remaining:
            rel = float(np.dot(query_vec, vectors[idx]))
            red = max((float(np.dot(vectors[idx], vectors[s])) for s in selected), default=0.0)
            score = lambda_ * rel - (1 - lambda_) * red
            if score > best_score:
                best_score, best_idx = score, idx
        selected.append(best_idx)
        remaining.remove(best_idx)
    return selected


def main():
    filenames, labels, vectors = get_all_embeddings()
    labels = np.asarray(labels)
    n = len(filenames)

    queries = list(LABEL_TO_PROMPT.items())  # (label, prompt) -- one query per category
    print(f"Sweeping lambda_ over {len(queries)} category-prompt queries, "
          f"corpus of {n} images, retrieve {K_RETRIEVE} -> rerank to {K_FINAL}\n")

    # Precompute the retrieval candidate pool per query once (independent of lambda_)
    query_vecs = []
    candidate_pools = []
    for label, prompt in queries:
        qv = model_cache.embed_text(prompt)
        sims = vectors @ qv
        top_idx = np.argsort(-sims)[:K_RETRIEVE].tolist()
        query_vecs.append(qv)
        candidate_pools.append(top_idx)

    raw = {}  # lambda_ -> (mean_relevance, mean_diversity)
    for lambda_ in LAMBDA_GRID:
        rels, divs = [], []
        for qv, pool in zip(query_vecs, candidate_pools):
            selected = mmr_rerank(qv, pool, vectors, K_FINAL, lambda_)
            rel = float(np.mean([np.dot(qv, vectors[i]) for i in selected]))
            div = len(set(labels[selected])) / K_FINAL
            rels.append(rel)
            divs.append(div)
        raw[lambda_] = (float(np.mean(rels)), float(np.mean(divs)))
        print(f"  lambda_={lambda_:.1f}  relevance@10={raw[lambda_][0]:.4f}  diversity@10={raw[lambda_][1]:.4f}")

    rel_vals = [raw[l][0] for l in LAMBDA_GRID]
    div_vals = [raw[l][1] for l in LAMBDA_GRID]

    def normalize(vals):
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [0.5] * len(vals)
        return [(v - lo) / (hi - lo) for v in vals]

    rel_norm = normalize(rel_vals)
    div_norm = normalize(div_vals)
    composite = {l: rn + dn for l, rn, dn in zip(LAMBDA_GRID, rel_norm, div_norm)}

    best_lambda = max(composite, key=composite.get)
    print("\nComposite scores (normalized relevance + normalized diversity):")
    for l in LAMBDA_GRID:
        marker = "  <-- best" if l == best_lambda else ""
        print(f"  lambda_={l:.1f}  composite={composite[l]:.3f}{marker}")
    print(f"\nWinning lambda_ = {best_lambda}")


if __name__ == "__main__":
    main()
