"""
Clustering algorithm/hyperparameter selection (Part A4 of the ML overhaul
plan) -- replaces the hardcoded `KMeans(n_clusters=8)` in cluster_images.py
with a data-driven choice.

What this does:
  1. Sweeps KMeans k over 4..16, plotting the elbow (inertia) and silhouette
     score (cosine metric, since CLIP embeddings are compared by cosine
     similarity everywhere else in this app) to pick k_best.
  2. Fits AgglomerativeClustering (cosine affinity, average linkage) at the
     same k_best, and DBSCAN (cosine metric) swept over eps, as comparison
     points -- so the final algorithm choice is justified by evidence
     rather than asserted.
  3. Scores all three candidates on silhouette, Davies-Bouldin, purity, and
     NMI against `verified_label` (the weak-but-verified ground truth from
     curation), and picks a winner by simple min-max-normalized composite
     rank across those four metrics.
  4. Saves a t-SNE 2D visualization (colored by true label and by the
     winning clustering) and the elbow/silhouette plot under ai/data/eval/,
     plus a machine-readable ai/data/best_clustering.json that
     cluster_images.py reads at runtime.

Caveat (documented, not hidden): with only ~205 images across 25 classes
(~8/class), NMI/purity against `verified_label` are informative but noisy,
and "verified_label" itself is a *category* label, not a guarantee that
visual clusters should align with it 1:1 (two categories can look visually
similar, e.g. "minimalist" vs "quiet_luxury"). Treat these as directional
evidence, not ground truth in the strict sense.

Usage:
    python ai/tune_clustering.py
Outputs:
    ai/data/best_clustering.json
    ai/data/eval/kmeans_elbow_silhouette.png
    ai/data/eval/tsne_embedding.png
"""
import json
import os
import sys
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score, davies_bouldin_score, normalized_mutual_info_score

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from embedding_cache import get_all_embeddings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVAL_DIR = os.path.join(DATA_DIR, "eval")
BEST_CLUSTERING_FILE = os.path.join(DATA_DIR, "best_clustering.json")

K_RANGE = list(range(4, 17))
DBSCAN_EPS_GRID = np.arange(0.05, 0.61, 0.05)
DBSCAN_MIN_SAMPLES = 3


def purity_score(true_labels, cluster_labels):
    true_labels = np.asarray(true_labels)
    cluster_labels = np.asarray(cluster_labels)
    correct = 0
    for c in set(cluster_labels):
        mask = cluster_labels == c
        if mask.sum() == 0:
            continue
        correct += Counter(true_labels[mask]).most_common(1)[0][1]
    return correct / len(true_labels)


def sweep_kmeans(vectors, verbose=True):
    inertias, silhouettes = [], []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(vectors)
        inertias.append(km.inertia_)
        sil = silhouette_score(vectors, km.labels_, metric="cosine")
        silhouettes.append(sil)
        if verbose:
            print(f"  k={k:2d}  inertia={km.inertia_:10.2f}  silhouette={sil:.4f}")

    k_best = K_RANGE[int(np.argmax(silhouettes))]

    os.makedirs(EVAL_DIR, exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(K_RANGE, inertias, "o-", color="tab:blue", label="inertia (elbow)")
    ax1.set_xlabel("k")
    ax1.set_ylabel("inertia", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(K_RANGE, silhouettes, "s-", color="tab:orange", label="silhouette (cosine)")
    ax2.set_ylabel("silhouette score", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")
    ax2.axvline(k_best, color="gray", linestyle="--", alpha=0.6)
    plt.title(f"KMeans elbow + silhouette sweep (best k={k_best} by silhouette)")
    fig.tight_layout()
    fig.savefig(os.path.join(EVAL_DIR, "kmeans_elbow_silhouette.png"), dpi=150)
    plt.close(fig)

    return k_best, dict(zip(K_RANGE, inertias)), dict(zip(K_RANGE, silhouettes))


def sweep_dbscan(vectors, verbose=True):
    best = None
    for eps in DBSCAN_EPS_GRID:
        db = DBSCAN(eps=eps, min_samples=DBSCAN_MIN_SAMPLES, metric="cosine").fit(vectors)
        labels = db.labels_
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        noise_frac = float((labels == -1).mean())
        if n_clusters < 2 or noise_frac > 0.5:
            if verbose:
                print(f"  eps={eps:.2f}  n_clusters={n_clusters}  noise={noise_frac:.2f}  (skipped)")
            continue
        mask = labels != -1
        sil = silhouette_score(vectors[mask], labels[mask], metric="cosine")
        if verbose:
            print(f"  eps={eps:.2f}  n_clusters={n_clusters}  noise={noise_frac:.2f}  silhouette={sil:.4f}")
        if best is None or sil > best["silhouette"]:
            best = {"eps": float(eps), "n_clusters": n_clusters, "noise_frac": noise_frac,
                    "silhouette": sil, "labels": labels}
    if best is None:
        # Fall back to the middle of the grid so downstream code still has
        # *something* to compare, but flag it clearly as not evidence-backed.
        eps = float(DBSCAN_EPS_GRID[len(DBSCAN_EPS_GRID) // 2])
        db = DBSCAN(eps=eps, min_samples=DBSCAN_MIN_SAMPLES, metric="cosine").fit(vectors)
        labels = db.labels_
        best = {"eps": eps, "n_clusters": len(set(labels)) - (1 if -1 in labels else 0),
                "noise_frac": float((labels == -1).mean()), "silhouette": None,
                "labels": labels, "fallback": True}
        print("  WARNING: no DBSCAN eps in the sweep produced >=2 clusters with <=50% noise; "
              "using a fallback eps. DBSCAN is not a strong candidate on this dataset.")
    return best


def evaluate_candidate(name, vectors, cluster_labels, true_labels):
    mask = np.asarray(cluster_labels) != -1  # exclude DBSCAN noise from silhouette/DB
    n_clusters_eff = len(set(np.asarray(cluster_labels)[mask]))
    metrics = {"name": name, "n_clusters": int(len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0))}
    if n_clusters_eff >= 2 and mask.sum() > n_clusters_eff:
        metrics["silhouette"] = float(silhouette_score(vectors[mask], np.asarray(cluster_labels)[mask], metric="cosine"))
        try:
            metrics["davies_bouldin"] = float(davies_bouldin_score(vectors[mask], np.asarray(cluster_labels)[mask]))
        except ValueError:
            metrics["davies_bouldin"] = None
    else:
        metrics["silhouette"] = None
        metrics["davies_bouldin"] = None
    metrics["purity"] = float(purity_score(true_labels, cluster_labels))
    metrics["nmi"] = float(normalized_mutual_info_score(true_labels, cluster_labels))
    # silhouette/davies_bouldin above are computed on non-noise points only,
    # which gives DBSCAN an unfair advantage if it dumps a large fraction of
    # the collection into the noise bucket -- track that fraction explicitly
    # so pick_winner() can penalize it (KMeans/Agglomerative always cover
    # 100% of points; DBSCAN often doesn't).
    metrics["coverage"] = float(mask.mean())
    return metrics


# A clustering that dumps more than this fraction of the collection into
# DBSCAN's noise bucket is disqualified from being the *deployed*
# algorithm, even if it wins on raw metrics -- see MAX_NOISE_FOR_DEPLOYMENT
# note in pick_winner() below.
MAX_NOISE_FOR_DEPLOYMENT = 0.30


def pick_winner(candidates):
    """Simple composite rank: min-max normalize each metric across
    candidates (inverting davies_bouldin, since lower is better there),
    average the five, pick the max among *eligible* candidates. Candidates
    missing silhouette/DB (degenerate clustering) are scored 0 on those
    metrics.

    `coverage` (fraction of images NOT dropped as DBSCAN noise) is included
    as its own metric so a DBSCAN config that scores well on
    silhouette/purity by discarding a chunk of the collection as noise
    doesn't automatically win over an algorithm that clusters everything.

    On this dataset, DBSCAN's best-by-silhouette eps (0.35) still leaves
    ~43% of images as noise -- even after the coverage penalty above, it
    can still out-score KMeans/Agglomerative on the composite, because its
    silhouette/purity/NMI are computed on the "easy" 57% it *did* cluster.
    That's not a fair trade for this app: every curated image needs a
    cluster assignment for the live "% of collection sharing this cluster"
    signal, so a clustering that leaves ~half the collection unassigned is
    impractical regardless of how clean its metrics look on the assigned
    half. MAX_NOISE_FOR_DEPLOYMENT hard-disqualifies any candidate whose
    noise fraction exceeds this from being the *winner* used for
    deployment -- it's still scored and reported for comparison.
    """
    keys_higher_better = ["silhouette", "purity", "nmi", "coverage"]
    key_lower_better = "davies_bouldin"

    def normalize(values):
        vals = [v for v in values if v is not None]
        if not vals or max(vals) == min(vals):
            return [0.5 if v is not None else 0.0 for v in values]
        lo, hi = min(vals), max(vals)
        return [(v - lo) / (hi - lo) if v is not None else 0.0 for v in values]

    scores = {c["name"]: 0.0 for c in candidates}
    for key in keys_higher_better:
        norm = normalize([c[key] for c in candidates])
        for c, n in zip(candidates, norm):
            scores[c["name"]] += n
    db_vals = [c[key_lower_better] for c in candidates]
    inv = [(-v if v is not None else None) for v in db_vals]
    norm_db = normalize(inv)
    for c, n in zip(candidates, norm_db):
        scores[c["name"]] += n
    n_metrics = len(keys_higher_better) + 1
    for c in candidates:
        scores[c["name"]] /= n_metrics

    eligible = [c for c in candidates if (1.0 - c["coverage"]) <= MAX_NOISE_FOR_DEPLOYMENT]
    if not eligible:
        eligible = candidates  # degenerate case: nothing meets the bar, fall back to raw best
    winner = max(eligible, key=lambda c: scores[c["name"]])
    disqualified = [c["name"] for c in candidates if c not in eligible]
    if disqualified:
        print(f"  (disqualified from deployment for >{MAX_NOISE_FOR_DEPLOYMENT:.0%} noise: {disqualified})")
    return winner["name"], scores


def plot_tsne(vectors, true_labels, winner_cluster_labels, winner_name):
    os.makedirs(EVAL_DIR, exist_ok=True)
    n = len(vectors)
    perplexity = max(5, min(30, n // 4))
    tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, init="pca")
    emb2d = tsne.fit_transform(vectors)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    unique_true = sorted(set(true_labels))
    cmap_true = matplotlib.colormaps["tab20"].resampled(max(len(unique_true), 1))
    for i, lbl in enumerate(unique_true):
        mask = np.array(true_labels) == lbl
        axes[0].scatter(emb2d[mask, 0], emb2d[mask, 1], s=18, color=cmap_true(i), label=lbl)
    axes[0].set_title("t-SNE colored by verified_label")
    axes[0].legend(fontsize=5, ncol=2, loc="upper right", framealpha=0.5)

    unique_clusters = sorted(set(winner_cluster_labels))
    cmap_c = matplotlib.colormaps["tab20"].resampled(max(len(unique_clusters), 1))
    for i, c in enumerate(unique_clusters):
        mask = np.array(winner_cluster_labels) == c
        label = "noise" if c == -1 else f"cluster {c}"
        axes[1].scatter(emb2d[mask, 0], emb2d[mask, 1], s=18, color=cmap_c(i), label=label)
    axes[1].set_title(f"t-SNE colored by winning clustering ({winner_name})")
    axes[1].legend(fontsize=6, ncol=2, loc="upper right", framealpha=0.5)

    fig.tight_layout()
    fig.savefig(os.path.join(EVAL_DIR, "tsne_embedding.png"), dpi=150)
    plt.close(fig)


def main():
    filenames, labels, vectors = get_all_embeddings()
    print(f"Loaded {len(filenames)} embeddings for clustering sweep\n")

    print("KMeans sweep (k=4..16):")
    k_best, inertias, silhouettes = sweep_kmeans(vectors)
    print(f"  -> k_best={k_best} (by silhouette)\n")

    km_final = KMeans(n_clusters=k_best, random_state=42, n_init=10).fit(vectors)

    agg = AgglomerativeClustering(n_clusters=k_best, metric="cosine", linkage="average").fit(vectors)

    print(f"\nDBSCAN eps sweep (min_samples={DBSCAN_MIN_SAMPLES}):")
    dbscan_result = sweep_dbscan(vectors)
    print(f"  -> eps={dbscan_result['eps']:.2f}, n_clusters={dbscan_result['n_clusters']}, "
          f"noise_frac={dbscan_result['noise_frac']:.2f}\n")

    candidates = [
        evaluate_candidate("kmeans", vectors, km_final.labels_, labels),
        evaluate_candidate("agglomerative", vectors, agg.labels_, labels),
        evaluate_candidate("dbscan", vectors, dbscan_result["labels"], labels),
    ]
    for c in candidates:
        print(c)

    winner_name, scores = pick_winner(candidates)
    print(f"\nComposite scores: {scores}")
    print(f"Winner: {winner_name}")

    cluster_labels_by_name = {
        "kmeans": km_final.labels_,
        "agglomerative": agg.labels_,
        "dbscan": dbscan_result["labels"],
    }
    plot_tsne(vectors, labels, cluster_labels_by_name[winner_name], winner_name)

    result = {
        "winner": winner_name,
        "kmeans": {"k": k_best, "metrics": next(c for c in candidates if c["name"] == "kmeans"),
                   "silhouette_by_k": silhouettes, "inertia_by_k": inertias},
        "agglomerative": {"k": k_best, "metrics": next(c for c in candidates if c["name"] == "agglomerative")},
        "dbscan": {"eps": dbscan_result["eps"], "min_samples": DBSCAN_MIN_SAMPLES,
                   "metrics": next(c for c in candidates if c["name"] == "dbscan")},
        "composite_scores": scores,
        "n_images": len(filenames),
        "n_true_labels": len(set(labels)),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BEST_CLUSTERING_FILE, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved winning clustering config to {BEST_CLUSTERING_FILE}")
    print(f"Plots saved under {EVAL_DIR}")


if __name__ == "__main__":
    main()
