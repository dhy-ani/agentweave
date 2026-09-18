"""
Cluster the curated fashion images into visual/aesthetic groups.

Previously hardcoded `KMeans(n_clusters=8)` over
datasets/vectors/blip_clip_combined.json -- which is the *same* stale,
partially-built vector file that the original generate_faiss_data.py bug
left at only 77/283 images (see backend/generate_faiss_data.py's
docstring). Running "tuned" clustering on top of that broken/incomplete
source would be pointless, so this now:

  1. Loads embeddings for the full curated set via ai.embedding_cache
     (the live model_cache singleton -- LoRA-tuned once the adapter
     exists, zero-shot base CLIP otherwise), instead of the stale JSON.
  2. Uses whichever algorithm + k (or eps, for DBSCAN) won the sweep in
     ai/tune_clustering.py (ai/data/best_clustering.json), instead of a
     hardcoded magic number. Falls back to KMeans(k=8) -- the original
     default -- with a printed warning if that file doesn't exist yet
     (e.g. a fresh checkout before tune_clustering.py has been run).
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from embedding_cache import get_all_embeddings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BEST_CLUSTERING_FILE = os.path.join(BASE_DIR, "data", "best_clustering.json")

DATASETS_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "datasets"))
OUTPUT_DIR = os.path.join(DATASETS_DIR, "vectors")
CLUSTER_MAP_FILE = os.path.join(OUTPUT_DIR, "cluster_map.json")
CLUSTER_GROUPS_FILE = os.path.join(OUTPUT_DIR, "cluster_groups.json")

# index -> cluster_id, in the SAME row order as datasets/curated_manifest.csv
# (which is also the order backend/generate_faiss_data.py embeds in, so FAISS
# index N and index_to_cluster.json["N"] refer to the same image). Consumed
# by routers/stylegenie.py for the "% of collection sharing this cluster"
# match-confidence signal.
INDEX_TO_CLUSTER_FILE = os.path.join(BASE_DIR, "data", "index_to_cluster.json")

DEFAULT_K = 8


def _load_tuned_config():
    if not os.path.exists(BEST_CLUSTERING_FILE):
        print(f"[cluster_images] WARNING: {BEST_CLUSTERING_FILE} not found -- "
              f"run ai/tune_clustering.py first. Falling back to untuned KMeans(k={DEFAULT_K}).")
        return {"algorithm": "kmeans", "k": DEFAULT_K}

    with open(BEST_CLUSTERING_FILE) as f:
        best = json.load(f)
    winner = best["winner"]
    if winner == "dbscan":
        return {"algorithm": "dbscan", "eps": best["dbscan"]["eps"],
                "min_samples": best["dbscan"]["min_samples"]}
    return {"algorithm": winner, "k": best[winner]["k"]}


def cluster(vectors, config):
    algo = config["algorithm"]
    if algo == "kmeans":
        from sklearn.cluster import KMeans
        model = KMeans(n_clusters=config["k"], random_state=42, n_init=10)
        return model.fit_predict(vectors), f"kmeans(k={config['k']})"
    if algo == "agglomerative":
        from sklearn.cluster import AgglomerativeClustering
        model = AgglomerativeClustering(n_clusters=config["k"], metric="cosine", linkage="average")
        return model.fit_predict(vectors), f"agglomerative(k={config['k']})"
    if algo == "dbscan":
        from sklearn.cluster import DBSCAN
        model = DBSCAN(eps=config["eps"], min_samples=config["min_samples"], metric="cosine")
        return model.fit_predict(vectors), f"dbscan(eps={config['eps']}, min_samples={config['min_samples']})"
    raise ValueError(f"Unknown clustering algorithm: {algo}")


def main():
    config = _load_tuned_config()
    filenames, labels, vectors = get_all_embeddings()
    print(f"Loaded {len(filenames)} embeddings. Clustering with: {config}")

    cluster_labels, desc = cluster(vectors, config)
    print(f"Clustered with {desc}")

    cluster_map = {}
    for filename, c in zip(filenames, cluster_labels):
        cluster_map.setdefault(str(int(c)), []).append(filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CLUSTER_MAP_FILE, "w") as f:
        json.dump(cluster_map, f, indent=2)
    print(f"Cluster map saved to {CLUSTER_MAP_FILE}")

    # cluster_groups.json mirrors cluster_map.json here (kept only for
    # backwards compatibility with older scripts that read this filename;
    # the mapping is already cluster_id -> [filenames]).
    with open(CLUSTER_GROUPS_FILE, "w") as f:
        json.dump(cluster_map, f, indent=2)
    print(f"Cluster groups saved to {CLUSTER_GROUPS_FILE}")

    index_to_cluster = {str(i): int(c) for i, c in enumerate(cluster_labels)}
    os.makedirs(os.path.dirname(INDEX_TO_CLUSTER_FILE), exist_ok=True)
    with open(INDEX_TO_CLUSTER_FILE, "w") as f:
        json.dump(index_to_cluster, f, indent=2)
    print(f"Index-to-cluster map saved to {INDEX_TO_CLUSTER_FILE}")

    for cid, files in sorted(cluster_map.items(), key=lambda kv: int(kv[0])):
        print(f"  cluster {cid}: {len(files)} images")


if __name__ == "__main__":
    main()
