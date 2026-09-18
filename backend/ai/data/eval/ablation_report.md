# AgentWeave ML ablation report

LoRA adapter active: **True**

Dataset: 205 curated images, 25 verified aesthetic categories.

## 1. Retrieval: zero-shot CLIP vs. LoRA-tuned

Relevance proxy: same `verified_label` as the query. Queries = held-out val split; corpus = full curated set (excluding the query itself).

| model | P@5 | mAP@5 | P@10 | mAP@10 |
|---|---|---|---|---|
| zero_shot | 0.487 | 0.427 | 0.359 | 0.366 |
| lora_tuned | 0.494 | 0.450 | 0.372 | 0.394 |

P@5 change from fine-tuning: **+0.006** (improvement)

## 2. Embedding separation (intra-class vs. inter-class cosine similarity)

| model | intra-class mean sim | inter-class mean sim | margin |
|---|---|---|---|
| zero_shot | 0.5951 | 0.4504 | 0.1447 |
| lora_tuned | 0.5158 | 0.3246 | 0.1912 |

Separation margin change from fine-tuning: **+0.0465**

## 3. Classifier head (logistic regression on current embeddings)

- Best C (grid search): 30.0
- Macro-F1: 0.597 +/- 0.052 (5-fold stratified CV, 199/205 images; excluded from CV for having <5 samples: [np.str_('preppy_school'), np.str_('retro_summer')])

## 4. Clustering

- Winning algorithm: **kmeans** (k=6)
- silhouette (cosine): 0.13362525403499603
- Davies-Bouldin: 2.738032417804534
- purity vs. verified_label: 0.273
- NMI vs. verified_label: 0.516
- composite scores across candidates: {'kmeans': 0.6071199280178496, 'agglomerative': 0.3494469305580393, 'dbscan': 0.765623712547851}

## Honesty notes

- ~205 images across 25 categories (~8/class) is a small-sample regime; none of the deltas above should be read as statistically significant in isolation.
- `verified_label` is a lightly-human-corrected weak label, not ground truth -- visually adjacent categories (e.g. `minimalist` vs. `quiet_luxury`) can legitimately confuse both the classifier and the clustering.
- If P@k or the separation margin did not improve, that's reported above as-is, not hidden.