"""
Small classifier head trained on frozen CLIP image embeddings to predict
the curated aesthetic category (verified_label) -- the concrete "trained
model" requirement from Part A3 of the ML overhaul plan, on top of what's
otherwise a pure retrieval system.

Embeddings come from ai.embedding_cache (which wraps ai.model_cache.embed_image)
-- i.e. they reflect whatever's currently loaded: LoRA-tuned once
backend/ai/data/lora_adapter/ exists, zero-shot base CLIP otherwise. Run
this *after* `finetune_clip_lora.py --train` so the classifier sits on top
of the fine-tuned embedding space.

Model choice: multinomial logistic regression (scikit-learn
LogisticRegression), not a shallow MLP. With ~205 images across 25 classes
(~8/class) on top of already-semantically-rich 512-d CLIP embeddings, a
linear head is the defensible choice -- an MLP's extra capacity would
almost certainly just memorize this dataset rather than generalize.

Evaluation: stratified 5-fold cross-validation, macro-F1 + confusion
matrix. Two classes are too small to stratify across 5 folds --
sklearn's StratifiedKFold requires >= n_splits members per class:
  - preppy_school (n=2), retro_summer (n=4)
Both are < 5, so they're excluded from the CV *metric* only (documented,
not silently dropped) -- they're still included when fitting the final
saved model on the full dataset, since there's no reason to withhold real
training data from the deployed classifier just because it's hard to
cross-validate.

Regularization strength `C` is tuned via a small grid search (a 1-D sweep
over ~8 points; Optuna would be overkill).

Usage:
    python ai/train_classifier.py
Outputs:
    ai/data/aesthetic_classifier.joblib  (dict: {"model", "label_encoder"})
    prints macro-F1 (mean +/- std across folds) and an aggregated confusion matrix
"""
import os
import sys

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, GridSearchCV, cross_val_predict
from sklearn.metrics import f1_score, confusion_matrix, classification_report
from sklearn.preprocessing import LabelEncoder

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from embedding_cache import get_all_embeddings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_FILE = os.path.join(DATA_DIR, "aesthetic_classifier.joblib")

MIN_CLASS_COUNT_FOR_CV = 5  # StratifiedKFold(n_splits=5) needs >= 5 per class
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0]


def evaluate_classifier(vectors, labels, n_splits=5, verbose=True):
    """Runs the CV + grid search described above.

    Returns a dict with: best_C, macro_f1_mean, macro_f1_std, per_fold_f1,
    confusion_matrix (list of lists), class_order (labels used in the CM),
    excluded_classes (dropped from CV for being too small), n_cv_samples.
    """
    labels = np.asarray(labels)
    counts = {l: int((labels == l).sum()) for l in set(labels)}
    excluded = sorted([l for l, c in counts.items() if c < n_splits])
    cv_mask = np.array([l not in excluded for l in labels])

    X_cv, y_cv_raw = vectors[cv_mask], labels[cv_mask]
    le = LabelEncoder().fit(y_cv_raw)
    y_cv = le.transform(y_cv_raw)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    grid = GridSearchCV(
        LogisticRegression(max_iter=5000),
        param_grid={"C": C_GRID},
        cv=skf,
        scoring="f1_macro",
        refit=False,
    )
    grid.fit(X_cv, y_cv)
    best_C = grid.best_params_["C"]

    # Per-fold macro-F1 at the chosen C, plus an aggregated confusion matrix
    # via cross_val_predict (each sample predicted only by the fold that
    # held it out).
    per_fold_f1 = []
    for train_idx, test_idx in skf.split(X_cv, y_cv):
        clf = LogisticRegression(C=best_C, max_iter=5000)
        clf.fit(X_cv[train_idx], y_cv[train_idx])
        pred = clf.predict(X_cv[test_idx])
        per_fold_f1.append(f1_score(y_cv[test_idx], pred, average="macro"))

    y_pred = cross_val_predict(
        LogisticRegression(C=best_C, max_iter=5000),
        X_cv, y_cv, cv=skf,
    )
    cm = confusion_matrix(y_cv, y_pred)
    report = classification_report(y_cv, y_pred, target_names=le.classes_, zero_division=0)

    result = {
        "best_C": best_C,
        "macro_f1_mean": float(np.mean(per_fold_f1)),
        "macro_f1_std": float(np.std(per_fold_f1)),
        "per_fold_f1": [float(x) for x in per_fold_f1],
        "confusion_matrix": cm.tolist(),
        "class_order": list(le.classes_),
        "excluded_classes": excluded,
        "n_cv_samples": int(cv_mask.sum()),
        "n_total_samples": int(len(labels)),
        "classification_report": report,
    }

    if verbose:
        print(f"Excluded from CV (fewer than {n_splits} samples): {excluded or 'none'}")
        print(f"CV over {result['n_cv_samples']}/{result['n_total_samples']} images, "
              f"{len(le.classes_)} classes")
        print(f"Best C (grid search): {best_C}")
        print(f"Macro-F1: {result['macro_f1_mean']:.3f} +/- {result['macro_f1_std']:.3f} "
              f"(per-fold: {[round(x, 3) for x in per_fold_f1]})")
        print("\nClassification report (aggregated out-of-fold predictions):")
        print(report)

    return result


def train_final_and_save(vectors, labels, best_C, verbose=True):
    """Fits on ALL curated data (including the CV-excluded tiny classes) and
    saves the model + label encoder together, since predict-time needs both."""
    le_full = LabelEncoder().fit(labels)
    y_full = le_full.transform(labels)
    clf = LogisticRegression(C=best_C, max_iter=5000)
    clf.fit(vectors, y_full)

    os.makedirs(DATA_DIR, exist_ok=True)
    joblib.dump({"model": clf, "label_encoder": le_full}, MODEL_FILE)
    if verbose:
        print(f"\nSaved final classifier (trained on all {len(labels)} images, "
              f"{len(le_full.classes_)} classes, C={best_C}) to {MODEL_FILE}")
    return clf, le_full


if __name__ == "__main__":
    filenames, labels, vectors = get_all_embeddings()
    result = evaluate_classifier(vectors, labels)
    train_final_and_save(vectors, labels, result["best_C"])
