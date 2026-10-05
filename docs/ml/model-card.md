# Model card: AgentWeave outfit retrieval and body-shape estimation

Format follows Mitchell et al., [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993) (FAT* 2019).

## 1. Model details

| | Outfit retrieval | Body-shape estimation |
|---|---|---|
| Architecture | CLIP ViT-B/32, checkpoint `laion/CLIP-ViT-B-32-laion2B-s34B-b79K`, with LoRA adapters merged in | YOLOv8n-pose (17 COCO keypoints) followed by hand-written ratio rules |
| Trained by this project | LoRA adapters only (rank 8, alpha 32, last 3 blocks, q/v projections, both towers) | Nothing; pretrained pose model, rules written by hand |
| Training objective | SupCon on image embeddings + image-to-category-prompt InfoNCE (text weight 0.157), temperature 0.177 | n/a |
| Hyperparameter search | Optuna TPE, 8 trials, stratified 3-fold CV; best lr 4.06e-5, weight decay 2.2e-4, dropout 0.022, batch size 8 | n/a |
| Serving format | ONNX, weight-only int8 (int4 token embeddings): vision 98.4 MB, text 55.7 MB | ONNX fp32, 13.5 MB |
| Code | `backend/ai/finetune_clip_lora.py`, `export_onnx.py`, `onnx_inference.py` | `backend/ai/body_shape_classifier.py` |

## 2. Intended use
- **Primary use:** rank a small, curated set of outfit photos against a user's context (occasion, weather, location, gender expression, body shape, occupation) for inspiration in a consumer style app.
- **Out of scope:** judging attractiveness or "flattering" fit, medical or body-composition assessment, identifying people, any decision with consequences beyond outfit inspiration.
- Body shape is one optional input among several and is never shown as a verdict. Shape typologies are unstable: a 1 cm change in tape position can move about 40% of women to a different class ([Loughborough University, 2021](https://www.lboro.ac.uk/media-centre/press-releases/2021/may/you-might-not-be-the-body-shape-you-think/)).

## 3. Factors
Results may vary by body size, skin tone, gender expression, pose, clothing coverage, image quality and the aesthetic categories present in the collection. None of these factors has been evaluated yet (see section 6).

## 4. Metrics
Relevance is approximated by "the retrieved image has the same verified aesthetic label as the query". That is a proxy, not human judgement of relevance.

| Metric | Why |
|---|---|
| Precision@5/@10, mAP@5/@10 | Users see the top of the list first |
| Intra- vs inter-class cosine margin | Whether fine-tuning separates aesthetics in embedding space |
| Macro-F1 of a logistic-regression probe | How linearly separable the categories are, weighting small classes equally |
| Cosine parity and top-10 overlap vs PyTorch fp32 | Whether export and quantization changed behaviour |
| Body-shape label agreement, ONNX vs ultralytics | Whether the pose export changed outcomes |
| ROC AUC of the match-score calibration | Whether the user-facing score separates same-aesthetic from different-aesthetic pairs |

## 5. Evaluation data and results
- Held-out validation split of 32 query images from the 205-image curated set (see the [dataset card](dataset-card.md)); retrieval is against the full set minus the query.

| Model | P@5 | mAP@5 | P@10 | mAP@10 | Separation margin |
|---|---|---|---|---|---|
| Zero-shot CLIP | 0.487 | 0.427 | 0.359 | 0.366 | 0.145 |
| LoRA-tuned CLIP (PyTorch fp32) | 0.494 | 0.450 | 0.372 | 0.394 | 0.191 |
| LoRA-tuned CLIP (ONNX int8, served) | 0.494 | 0.459 | n/a | n/a | n/a |

- Logistic-regression probe: macro-F1 0.597 ± 0.052 (stratified 5-fold, 199 images; two classes with fewer than 5 images excluded from CV). Weakest classes: `korean_street` and `officewear` (F1 0.00), which overlap visually with neighbouring categories.
- ONNX parity: image cosine 0.998 mean / 0.975 min, text 0.994 / 0.987, top-10 overlap 0.94 (text to image) and 0.96 (image to image).
- Pose: mean keypoint error 0.004 (normalised units); body-shape label agreement 99.5% on 197 images with a detected person.
- User-facing match score: raw cosine is mapped to its percentile among same-aesthetic pairs, separately for text and image queries (`backend/ai/calibrate_scores.py`). Text calibration uses category prompts as queries, which are shorter than real user prompts, so it is an approximation. ROC AUC 0.95 for text and 0.87 for image.
- Sources: [ablation_report.md](../../backend/ai/data/eval/ablation_report.md), [onnx_parity.md](../../backend/ai/data/eval/onnx_parity.md).

## 6. Ethical considerations and caveats
- **Small sample.** 205 images, about 8 per class; none of the improvements above is statistically significant on its own.
- **Data provenance.** Images were scraped from Pinterest with unverified licences. Fine for a learning project; must be replaced with licensed data before any commercial use.
- **Representation.** No audit yet of how the collection represents different body sizes, skin tones or ages; recommendations can only be as inclusive as the collection.
- **Body-image sensitivity.** The body-shape rules were written by hand and never validated against measured bodies. The UI frames the result neutrally, and the photo is processed in memory and not stored.
- **Proxy relevance.** Labels were derived from search terms and lightly corrected by hand; they are weak labels, not ground truth.

## 7. Recommendations
1. Run a usability study with human relevance judgements to validate the label proxy.
2. Audit the collection for body-size and skin-tone coverage and rebalance it.
3. Make the body-photo step skippable, with manual shape selection or "prefer not to say".
4. Replace scraped images with licensed or user-contributed images.
