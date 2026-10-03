# Dataset card: AgentWeave curated aesthetics set

Loosely follows Gebru et al., [Datasheets for Datasets](https://arxiv.org/abs/1803.09010).

## Motivation
A small set of outfit photos covering 25 named aesthetics (for example boho beach, quiet luxury, techwear, cottagecore), used as both the retrieval collection and the training data for the LoRA adapters.

## Composition
- **Size:** 205 JPEG images after curation, from 283 raw images.
- **Labels:** one `verified_label` per image, in `datasets/curated_manifest.csv`.
- **Splits:** train and validation, in `backend/ai/data/split.json`; 32 images are held out for validation.
- **Format:** longest side at most 1024 px, JPEG quality 85, EXIF stripped (`datasets/processedImages/`).

## Collection
Images were collected with a Selenium scraper (`datasets/scrape_pinterest.py`) running 24 aesthetic search queries on Pinterest, up to about 20 images per query. Initial labels came from the search query. **Licences were not checked**, which is acceptable only for a non-commercial learning project.

## Curation (`datasets/curate_dataset.py`)

| Step | Rule |
|---|---|
| Exact duplicates | MD5 hash match (8 found in the raw set) |
| Near duplicates | Perceptual hash, Hamming distance ≤ 6 |
| Too small | Either side under 200 px |
| Blurry | Laplacian variance under 60 |
| Collages and banners | Aspect ratio below 0.4 or above 2.6 |
| Label check | CLIP zero-shot prediction compared with the search-term label; 59 disagreements flagged (`flagged_for_review.csv`), 31 labels corrected by hand (`label_overrides.csv`) |
| Normalisation | Resize, strip EXIF, re-encode |

## Known gaps
- **Text-heavy graphics.** At least one infographic-style image (large overlaid text) passed every filter; text or OCR density is not yet a curation criterion.
- **Small classes.** Several classes have fewer than 5 images (for example `preppy_school`, `retro_summer`), which limits cross-validation.
- **Representation not audited.** Body size, skin tone, age and gender expression across the set have not been checked.
- **Weak labels.** Labels come from search terms, lightly corrected; visually adjacent aesthetics (for example minimalist and quiet luxury) overlap.

## Uses
- **Supported:** retrieval collection and few-shot adaptation research for this app.
- **Not supported:** commercial use, redistribution, or training models intended to make judgements about people.

## Maintenance
To regenerate everything:
1. Rerun `curate_dataset.py`.
2. Rerun `backend/ai/build_corpus_embeddings.py` so the served embeddings match the curated set and the deployed model.
3. Rerun the evaluation scripts.
