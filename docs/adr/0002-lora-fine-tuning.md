# 0002. Adapt CLIP with LoRA instead of full fine-tuning

Status: Accepted

## Context
Zero-shot CLIP already separates fashion aesthetics reasonably well, but the product owner wanted the backbone adapted to the app's 25 aesthetic categories. The curated set has 205 images (about 8 per class). Full fine-tuning of CLIP ViT-B/32 (about 150M parameters) on that little data would overfit and erode the pretrained representation.

## Decision
Freeze the backbone and train LoRA adapters (rank 8) on the query and value projections of the last three transformer blocks of both the vision and text towers. Loss: supervised contrastive (SupCon) on image embeddings plus an image-to-category-prompt InfoNCE term so the text tower is adapted too. Tune hyperparameters with Optuna (TPE, 8 trials, stratified 3-fold CV objective, chosen because CPU-only training made larger sweeps impractical). Use random-crop, flip and colour-jitter augmentation, weight decay and early stopping.

## Consequences
- Small, regularised update: retrieval P@5 0.487 to 0.494, mAP@5 0.427 to 0.450, class-separation margin 0.145 to 0.191 on the held-out split. Gains are modest and not significant at this sample size; the ablation report says so.
- The adapter is merged into the weights before export, so serving pays no extra cost.
- Eight trials is a narrow search; with a GPU the next step is a wider sweep and k-fold early stopping for the final model.
