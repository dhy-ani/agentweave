"""
The ablation report that justifies the whole ML overhaul (Part A6 of the
plan): does the LoRA fine-tune actually help retrieval, on top of what a
classifier head and clustering already show?

Compares zero-shot base CLIP (laion/CLIP-ViT-B-32-laion2B-s34B-b79K, no
adapter) against the LoRA-tuned model (ai/model_cache's current state --
requires backend/ai/data/lora_adapter/ to exist; run
`finetune_clip_lora.py --train` first or this reduces to a zero-shot vs.
zero-shot no-op) on three axes:

  1. Retrieval: Precision@k / mAP@k on the held-out val split (from
     ai/data_split.py), using "same verified_label" as the relevance
     proxy. Queries = val split; corpus = the full curated set (mirrors
     how the live FAISS index actually works -- it indexes everything).
  2. Embedding separation: mean intra-class vs. inter-class cosine
     similarity, over the full curated set, before vs. after fine-tuning.
  3. Pulls in the classifier macro-F1 (train_classifier.py, re-evaluated
     on whichever embeddings are currently active) and the clustering
     metrics (tune_clustering.py's saved ai/data/best_clustering.json) so
     everything lives in one summary.

Honesty note (per the project's own ground rules): with ~205 images across
25 classes, none of these numbers are statistically strong evidence in the
rigorous sense -- they're small-sample directional signals. If the
fine-tune doesn't clearly beat zero-shot on some axis, this script reports
that plainly rather than cherry-picking.

Usage:
    python ai/evaluate_retrieval.py
Outputs:
    ai/data/eval/ablation_report.md
    prints the same report to stdout
"""
import json
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from embedding_cache import get_all_embeddings, zero_shot_embedder
from data_split import get_splits, load_manifest
os.environ.setdefault("AGENTWEAVE_BACKEND", "torch")
import model_cache
from train_classifier import evaluate_classifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVAL_DIR = os.path.join(DATA_DIR, "eval")
BEST_CLUSTERING_FILE = os.path.join(DATA_DIR, "best_clustering.json")
REPORT_FILE = os.path.join(EVAL_DIR, "ablation_report.md")

K_VALUES = [5, 10]


def _cosine_sim_matrix(vectors):
    # vectors are already L2-normalized by model_cache.embed_image, but
    # normalize again defensively (zero-shot embedder does too).
    norm = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    return norm @ norm.T


def precision_and_ap_at_k(sim, labels, query_indices, k):
    n = len(labels)
    precisions, aps = [], []
    for qi in query_indices:
        row = sim[qi].copy()
        row[qi] = -np.inf
        order = np.argsort(-row)[:k]
        rel = [1 if labels[j] == labels[qi] else 0 for j in order]
        precisions.append(sum(rel) / k)

        total_rel = sum(1 for j in range(n) if j != qi and labels[j] == labels[qi])
        denom = min(k, total_rel) if total_rel > 0 else 1
        hits, ap = 0, 0.0
        for rank, r in enumerate(rel, start=1):
            if r:
                hits += 1
                ap += hits / rank
        aps.append(ap / denom if total_rel > 0 else 0.0)
    return float(np.mean(precisions)), float(np.mean(aps))


def intra_inter_class_margin(sim, labels):
    labels = np.asarray(labels)
    n = len(labels)
    intra, inter = [], []
    for i in range(n):
        for j in range(i + 1, n):
            (intra if labels[i] == labels[j] else inter).append(sim[i, j])
    intra_mean = float(np.mean(intra)) if intra else float("nan")
    inter_mean = float(np.mean(inter)) if inter else float("nan")
    return intra_mean, inter_mean, intra_mean - inter_mean


def run_retrieval_ablation(zero_shot, tuned, labels, val_files, filenames):
    val_idx = [filenames.index(f) for f in val_files]
    results = {}
    for name, vectors in [("zero_shot", zero_shot), ("lora_tuned", tuned)]:
        sim = _cosine_sim_matrix(vectors)
        per_k = {}
        for k in K_VALUES:
            p, ap = precision_and_ap_at_k(sim, labels, val_idx, k)
            per_k[k] = {"precision": p, "map": ap}
        intra, inter, margin = intra_inter_class_margin(sim, labels)
        results[name] = {"retrieval": per_k, "intra_class_mean_sim": intra,
                          "inter_class_mean_sim": inter, "separation_margin": margin}
    return results


def main():
    lora_active = model_cache.is_lora_active()
    if not lora_active:
        print("WARNING: no LoRA adapter is currently loaded -- the 'lora_tuned' arm "
              "below will actually just be zero-shot CLIP again. Run "
              "`finetune_clip_lora.py --train` first for a meaningful ablation.\n")

    filenames, labels, tuned_vectors = get_all_embeddings(tag="lora" if lora_active else "zeroshot_base")
    zs_filenames, zs_labels, zero_shot_vectors = get_all_embeddings(
        embedder=zero_shot_embedder(), tag="zeroshot_fixed"
    )
    assert filenames == zs_filenames, "embedding caches are out of sync (manifest changed?)"

    _, val_files, _ = get_splits()
    print(f"Retrieval ablation: {len(val_files)} val queries against {len(filenames)}-image corpus\n")

    retrieval = run_retrieval_ablation(zero_shot_vectors, tuned_vectors, labels, val_files, filenames)

    print("Classifier (evaluated on CURRENT embeddings, i.e. LoRA-tuned if active):")
    clf_result = evaluate_classifier(tuned_vectors, labels, verbose=False)
    print(f"  macro-F1 = {clf_result['macro_f1_mean']:.3f} +/- {clf_result['macro_f1_std']:.3f} "
          f"(best C={clf_result['best_C']})\n")

    clustering = None
    if os.path.exists(BEST_CLUSTERING_FILE):
        with open(BEST_CLUSTERING_FILE) as f:
            clustering = json.load(f)
    else:
        print("NOTE: ai/data/best_clustering.json not found -- run tune_clustering.py "
              "to include clustering metrics in the report.\n")

    # ── Build report ──────────────────────────────────────────────────
    lines = []
    lines.append("# AgentWeave ML ablation report\n")
    lines.append(f"LoRA adapter active: **{lora_active}**\n")
    lines.append(f"Dataset: {len(filenames)} curated images, {len(set(labels))} verified aesthetic categories.\n")

    lines.append("## 1. Retrieval: zero-shot CLIP vs. LoRA-tuned\n")
    lines.append("Relevance proxy: same `verified_label` as the query. "
                  "Queries = held-out val split; corpus = full curated set (excluding the query itself).\n")
    lines.append("| model | P@5 | mAP@5 | P@10 | mAP@10 |")
    lines.append("|---|---|---|---|---|")
    for name in ["zero_shot", "lora_tuned"]:
        r = retrieval[name]["retrieval"]
        lines.append(f"| {name} | {r[5]['precision']:.3f} | {r[5]['map']:.3f} | "
                      f"{r[10]['precision']:.3f} | {r[10]['map']:.3f} |")
    p5_delta = retrieval["lora_tuned"]["retrieval"][5]["precision"] - retrieval["zero_shot"]["retrieval"][5]["precision"]
    lines.append(f"\nP@5 change from fine-tuning: **{p5_delta:+.3f}**"
                 + (" (improvement)" if p5_delta > 0 else " (no improvement / regression -- reported as-is)"))

    lines.append("\n## 2. Embedding separation (intra-class vs. inter-class cosine similarity)\n")
    lines.append("| model | intra-class mean sim | inter-class mean sim | margin |")
    lines.append("|---|---|---|---|")
    for name in ["zero_shot", "lora_tuned"]:
        r = retrieval[name]
        lines.append(f"| {name} | {r['intra_class_mean_sim']:.4f} | {r['inter_class_mean_sim']:.4f} | {r['separation_margin']:.4f} |")
    margin_delta = retrieval["lora_tuned"]["separation_margin"] - retrieval["zero_shot"]["separation_margin"]
    lines.append(f"\nSeparation margin change from fine-tuning: **{margin_delta:+.4f}**")

    lines.append("\n## 3. Classifier head (logistic regression on current embeddings)\n")
    lines.append(f"- Best C (grid search): {clf_result['best_C']}")
    lines.append(f"- Macro-F1: {clf_result['macro_f1_mean']:.3f} +/- {clf_result['macro_f1_std']:.3f} "
                  f"(5-fold stratified CV, {clf_result['n_cv_samples']}/{clf_result['n_total_samples']} images; "
                  f"excluded from CV for having <5 samples: {clf_result['excluded_classes'] or 'none'})")

    lines.append("\n## 4. Clustering\n")
    if clustering:
        winner = clustering["winner"]
        m = clustering[winner]["metrics"]
        lines.append(f"- Winning algorithm: **{winner}** "
                      f"({'k=' + str(clustering[winner]['k']) if winner != 'dbscan' else 'eps=' + str(clustering['dbscan']['eps'])})")
        lines.append(f"- silhouette (cosine): {m['silhouette']}")
        lines.append(f"- Davies-Bouldin: {m['davies_bouldin']}")
        lines.append(f"- purity vs. verified_label: {m['purity']:.3f}")
        lines.append(f"- NMI vs. verified_label: {m['nmi']:.3f}")
        lines.append(f"- composite scores across candidates: {clustering['composite_scores']}")
    else:
        lines.append("- (not available -- run `tune_clustering.py`)")

    lines.append("\n## Honesty notes\n")
    lines.append("- ~205 images across 25 categories (~8/class) is a small-sample regime; "
                  "none of the deltas above should be read as statistically significant in isolation.")
    lines.append("- `verified_label` is a lightly-human-corrected weak label, not ground truth -- "
                  "visually adjacent categories (e.g. `minimalist` vs. `quiet_luxury`) can legitimately "
                  "confuse both the classifier and the clustering.")
    lines.append("- If P@k or the separation margin did not improve, that's reported above as-is, not hidden.")

    report = "\n".join(lines)
    os.makedirs(EVAL_DIR, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write(report)

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)
    print(f"\nSaved report to {REPORT_FILE}")


if __name__ == "__main__":
    main()
