"""
Data curation pipeline for the AgentWeave fashion dataset (Part A2 of the ML
overhaul plan).

Two-phase design because weak-label verification needs a human (Claude) in
the loop for the flagged subset only:

  Phase 1 (`--phase1`, default): MD5 exact-dedup -> perceptual-hash near-dedup
      -> quality filter (resolution / blur / aspect ratio) -> resize+re-encode
      survivors into datasets/processedImages/ -> zero-shot CLIP classify each
      survivor against the 26 category prompts -> write:
        datasets/flagged_for_review.csv   (filename, filename_label, clip_label, clip_confidence)
        datasets/curated_manifest_draft.csv (filename, verified_label, width, height, phash)
      For flagged rows, verified_label in the draft is left as the filename
      label but the row is marked needs_review=1.

  Manual step (outside this script): Claude reads datasets/label_overrides.csv
      is produced by hand after visually inspecting every flagged image,
      columns: filename, corrected_label.

  Phase 2 (`--finalize`): merge datasets/label_overrides.csv into the draft
      manifest and write the final datasets/curated_manifest.csv.

No re-scraping. No re-processing of images in --finalize (that already
happened in phase 1); it only touches the manifest labels.
"""
import argparse
import csv
import hashlib
import os
import sys

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageOps

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from category_labels import LABEL_TO_PROMPT, LABELS, label_from_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "rawImages")
PROCESSED_DIR = os.path.join(BASE_DIR, "processedImages")
DRAFT_MANIFEST = os.path.join(BASE_DIR, "curated_manifest_draft.csv")
FLAGGED_CSV = os.path.join(BASE_DIR, "flagged_for_review.csv")
OVERRIDES_CSV = os.path.join(BASE_DIR, "label_overrides.csv")
FINAL_MANIFEST = os.path.join(BASE_DIR, "curated_manifest.csv")

# Quality thresholds
MIN_DIM = 200                 # px, drop anything smaller on either side
BLUR_VAR_THRESHOLD = 60.0     # Laplacian variance below this -> too blurry
MIN_ASPECT = 0.4              # w/h below this -> likely a tall collage/screenshot
MAX_ASPECT = 2.6              # w/h above this -> likely a wide banner/collage

MAX_DIM = 1024                # preprocessing: longest side
JPEG_QUALITY = 85

PHASH_HAMMING_THRESHOLD = 6   # <= this distance between phashes -> near-duplicate


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def laplacian_variance(pil_img):
    gray = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def dedup_exact(files):
    """Drop exact MD5 duplicates, keeping the first occurrence (sorted)."""
    seen_hashes = {}
    kept, dropped = [], []
    for fname in sorted(files):
        path = os.path.join(RAW_DIR, fname)
        h = md5_of(path)
        if h in seen_hashes:
            dropped.append((fname, f"exact duplicate of {seen_hashes[h]}"))
        else:
            seen_hashes[h] = fname
            kept.append(fname)
    return kept, dropped


def dedup_near(files):
    """Drop perceptual near-duplicates (phash hamming distance <= threshold)."""
    hashes = {}
    kept, dropped = [], []
    for fname in files:
        try:
            with Image.open(os.path.join(RAW_DIR, fname)) as img:
                ph = imagehash.phash(img)
        except Exception as e:
            dropped.append((fname, f"unreadable: {e}"))
            continue
        is_dup = False
        for kept_fname, kept_hash in hashes.items():
            if ph - kept_hash <= PHASH_HAMMING_THRESHOLD:
                dropped.append((fname, f"near-duplicate of {kept_fname} (hamming={ph - kept_hash})"))
                is_dup = True
                break
        if not is_dup:
            hashes[fname] = ph
            kept.append(fname)
    return kept, dropped, hashes


def quality_filter(files):
    kept, dropped = [], []
    for fname in files:
        path = os.path.join(RAW_DIR, fname)
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                w, h = img.size
                if w < MIN_DIM or h < MIN_DIM:
                    dropped.append((fname, f"too small ({w}x{h})"))
                    continue
                aspect = w / h
                if aspect < MIN_ASPECT or aspect > MAX_ASPECT:
                    dropped.append((fname, f"extreme aspect ratio ({aspect:.2f})"))
                    continue
                blur = laplacian_variance(img)
                if blur < BLUR_VAR_THRESHOLD:
                    dropped.append((fname, f"too blurry (lap_var={blur:.1f})"))
                    continue
        except Exception as e:
            dropped.append((fname, f"unreadable: {e}"))
            continue
        kept.append(fname)
    return kept, dropped


def preprocess_and_save(files):
    """Resize to MAX_DIM longest side, strip EXIF, re-encode as JPEG q=85."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    dims = {}
    for fname in files:
        src = os.path.join(RAW_DIR, fname)
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)  # bake in orientation, then EXIF is dropped on save
            img = img.convert("RGB")
            w, h = img.size
            scale = MAX_DIM / max(w, h)
            if scale < 1.0:
                img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
            out_name = os.path.splitext(fname)[0] + ".jpg"
            out_path = os.path.join(PROCESSED_DIR, out_name)
            img.save(out_path, "JPEG", quality=JPEG_QUALITY)  # PIL save() omits EXIF unless re-added
            dims[out_name] = img.size
    return dims


def zero_shot_verify(files, top_n=3):
    """Run zero-shot CLIP classification of each processed image against the
    26 category prompts; return {filename: (top1_label, top1_confidence, top_n_labels)}.

    26 of these aesthetic categories are semantically close (e.g. quiet_luxury
    vs. minimalist vs. monochrome, or boho_beach vs. cottagecore vs.
    summer_festival), so raw top-1 disagreement with the filename label is
    common even for correctly-labeled images and is too noisy a flag on its
    own. We flag for manual review only when the filename label doesn't even
    appear in CLIP's top-`top_n` predictions -- a much stronger signal of an
    actual mislabel rather than category overlap.
    """
    import torch
    import open_clip as oc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = oc.create_model_and_transforms(
        "ViT-B-32", pretrained="laion400m_e32", device=device
    )
    model.eval()
    tokenizer = oc.get_tokenizer("ViT-B-32")

    prompts = [LABEL_TO_PROMPT[l] for l in LABELS]
    with torch.no_grad():
        text_tokens = tokenizer(prompts).to(device)
        text_feats = model.encode_text(text_tokens)
        text_feats /= text_feats.norm(dim=-1, keepdim=True)

    results = {}
    with torch.no_grad():
        for fname in files:
            img = Image.open(os.path.join(PROCESSED_DIR, fname)).convert("RGB")
            inp = preprocess(img).unsqueeze(0).to(device)
            feat = model.encode_image(inp)
            feat /= feat.norm(dim=-1, keepdim=True)
            sims = (feat @ text_feats.T).squeeze(0)
            probs = torch.softmax(sims * 100.0, dim=0)  # CLIP-style temperature
            order = torch.argsort(probs, descending=True)
            top_idx = [int(i) for i in order[:top_n]]
            top_labels = [LABELS[i] for i in top_idx]
            top1 = top_idx[0]
            results[fname] = (LABELS[top1], float(probs[top1].item()), top_labels)
    return results


def phase1():
    raw_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"[curate] {len(raw_files)} raw images found")

    kept, exact_dupes = dedup_exact(raw_files)
    print(f"[curate] exact-MD5 dedup: dropped {len(exact_dupes)} -> {len(kept)} remain")
    for fname, reason in exact_dupes:
        print(f"    drop {fname}: {reason}")

    kept, near_dupes, phashes = dedup_near(kept)
    print(f"[curate] perceptual-hash dedup: dropped {len(near_dupes)} -> {len(kept)} remain")
    for fname, reason in near_dupes:
        print(f"    drop {fname}: {reason}")

    kept, quality_dropped = quality_filter(kept)
    print(f"[curate] quality filter: dropped {len(quality_dropped)} -> {len(kept)} remain")
    for fname, reason in quality_dropped:
        print(f"    drop {fname}: {reason}")

    print(f"[curate] preprocessing {len(kept)} survivors -> {PROCESSED_DIR}")
    dims = preprocess_and_save(kept)
    processed_names = list(dims.keys())

    print(f"[curate] zero-shot CLIP verification of {len(processed_names)} images against "
          f"{len(LABELS)} category prompts...")
    predictions = zero_shot_verify(processed_names)

    draft_rows = []
    flagged_rows = []
    for out_name in processed_names:
        # map back to the original raw filename (same stem, possibly different ext) for label derivation
        raw_stem = os.path.splitext(out_name)[0]
        raw_candidates = [f for f in kept if os.path.splitext(f)[0] == raw_stem]
        raw_fname = raw_candidates[0] if raw_candidates else out_name
        filename_label = label_from_filename(raw_fname)
        clip_label, clip_conf, top_labels = predictions[out_name]
        w, h = dims[out_name]
        ph = str(phashes.get(raw_fname, ""))
        needs_review = filename_label not in top_labels
        draft_rows.append({
            "filename": out_name,
            "verified_label": filename_label,  # placeholder; corrected in --finalize if flagged
            "width": w,
            "height": h,
            "phash": ph,
            "needs_review": int(needs_review),
        })
        if needs_review:
            flagged_rows.append({
                "filename": out_name,
                "filename_label": filename_label,
                "clip_label": clip_label,
                "clip_confidence": round(clip_conf, 4),
                "clip_top3": "|".join(top_labels),
            })

    with open(DRAFT_MANIFEST, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "verified_label", "width", "height", "phash", "needs_review"])
        writer.writeheader()
        writer.writerows(draft_rows)

    with open(FLAGGED_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "filename_label", "clip_label", "clip_confidence", "clip_top3"])
        writer.writeheader()
        writer.writerows(flagged_rows)

    print(f"[curate] wrote {DRAFT_MANIFEST} ({len(draft_rows)} rows)")
    print(f"[curate] wrote {FLAGGED_CSV} ({len(flagged_rows)} rows flagged for manual review)")
    print(f"[curate] {len(flagged_rows)}/{len(draft_rows)} images "
          f"({100.0*len(flagged_rows)/max(1,len(draft_rows)):.1f}%) need manual label review.")
    print("[curate] Next: manually inspect each flagged image and write "
          f"{OVERRIDES_CSV} (filename, corrected_label), then run --finalize.")


def finalize():
    if not os.path.exists(DRAFT_MANIFEST):
        raise SystemExit("Run --phase1 first.")
    with open(DRAFT_MANIFEST, newline="") as f:
        rows = list(csv.DictReader(f))

    overrides = {}
    if os.path.exists(OVERRIDES_CSV):
        with open(OVERRIDES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                overrides[row["filename"]] = row["corrected_label"]
        print(f"[finalize] loaded {len(overrides)} manual label overrides")
    else:
        print(f"[finalize] WARNING: no {OVERRIDES_CSV} found; flagged rows keep filename-derived label")

    n_corrected = 0
    n_removed = 0
    final_rows = []
    for row in rows:
        if row["filename"] in overrides:
            new_label = overrides[row["filename"]]
            if new_label.strip().upper() == "REMOVE":
                # manual review found this sample isn't usable for any category
                # (e.g. a product-shot t-shirt graphic with no fashion-outfit content)
                n_removed += 1
                stale_path = os.path.join(PROCESSED_DIR, row["filename"])
                if os.path.exists(stale_path):
                    os.remove(stale_path)
                continue
            if new_label != row["verified_label"]:
                n_corrected += 1
            row["verified_label"] = new_label
        del row["needs_review"]
        final_rows.append(row)

    with open(FINAL_MANIFEST, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "verified_label", "width", "height", "phash"])
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"[finalize] applied {n_corrected} corrections from manual review")
    print(f"[finalize] removed {n_removed} samples marked REMOVE during manual review")
    print(f"[finalize] wrote {FINAL_MANIFEST} ({len(final_rows)} rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--phase1", action="store_true", help="dedup+filter+preprocess+flag (default)")
    group.add_argument("--finalize", action="store_true", help="merge manual overrides into final manifest")
    args = parser.parse_args()

    if args.finalize:
        finalize()
    else:
        phase1()
