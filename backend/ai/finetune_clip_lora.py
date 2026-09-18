"""
LoRA fine-tuning of the CLIP backbone (Part A3 of the ML overhaul plan).

Why LoRA instead of full fine-tuning: ~205 curated images across 25
categories (~8/class) is far too little data to fully fine-tune CLIP's
~150M parameters without destroying the pretrained representation. LoRA
adapters on the last few attention blocks of both towers let the backbone
itself shift towards this dataset's aesthetic categories while keeping the
vast majority of pretrained weights frozen -- a defensible way to satisfy
"fine-tune the backbone itself" at this data scale.

Loss: a combination of
  1. Supervised Contrastive loss (SupCon, Khosla et al. 2020) over augmented
     image embeddings within a batch, using verified_label as the positive/
     negative signal -- multiple images of the same aesthetic category are
     pulled together, different categories pushed apart.
  2. A multi-positive image<->text InfoNCE loss using each category's CLIP
     text prompt as the text anchor, so the text tower's LoRA adapter is
     trained jointly rather than left along for the ride.

Regularization for the small-data regime: LoRA rank kept small (4-8),
`lora_dropout`, weight decay on the adapter params, random-crop/flip/color-
jitter augmentation (multiplies effective sample count), and early stopping
on a held-out validation split (backend/ai/data_split.py).

Pragmatic scope note: the plan calls for "early stopping via k-fold" as part
of the regularization story. Full k-fold retraining of a transformer (even a
tiny LoRA adapter) for every fold, on top of a 20-40 trial Optuna sweep, was
too slow for this CPU-only box within a reasonable session. Compromise used
here: k-fold CV (default k=3) is used during the Optuna *hyperparameter
search* (--optuna) to get a more robust objective estimate per trial, since
those trials are deliberately short (few epochs). The *final* adapter
(--train, using the winning hyperparameters) is trained once on the train
split with early stopping (patience) against the val split, which is the
standard and much cheaper way to prevent overfitting for the actual deployed
model. This is documented here rather than silently dropped.

Usage:
    python ai/finetune_clip_lora.py --optuna 12   # hyperparameter sweep -> ai/data/best_lora_hparams.json
    python ai/finetune_clip_lora.py --train        # train final adapter -> ai/data/lora_adapter/
"""
import argparse
import json
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms as T

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "datasets"))
from data_split import get_splits, label_map, PROCESSED_DIR
from category_labels import LABEL_TO_PROMPT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ADAPTER_DIR = os.path.join(DATA_DIR, "lora_adapter")
BEST_HPARAMS_FILE = os.path.join(DATA_DIR, "best_lora_hparams.json")
CHECKPOINT = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"

device = "cuda" if torch.cuda.is_available() else "cpu"

DEFAULT_HPARAMS = {
    "lora_rank": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.1,
    "lr": 5e-5,
    "weight_decay": 0.01,
    "temperature": 0.07,
    "batch_size": 16,
    "text_loss_weight": 0.5,
}


# ── Augmentation ──────────────────────────────────────────────────────────

def build_augment():
    return T.Compose([
        T.RandomResizedCrop(224, scale=(0.7, 1.0)),
        T.RandomHorizontalFlip(p=0.5),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.02),
    ])


class FashionDataset(Dataset):
    def __init__(self, filenames, labels, augment=True):
        self.filenames = filenames
        self.labels = labels
        self.augment = build_augment() if augment else None

    def __len__(self):
        return len(self.filenames)

    def __getitem__(self, idx):
        fname = self.filenames[idx]
        img = Image.open(os.path.join(PROCESSED_DIR, fname)).convert("RGB")
        if self.augment:
            img = self.augment(img)
        return img, self.labels[idx]


def collate(batch, processor):
    imgs, labels = zip(*batch)
    pixel_values = processor(images=list(imgs), return_tensors="pt")["pixel_values"]
    return pixel_values, list(labels)


# ── Model setup ───────────────────────────────────────────────────────────

def build_lora_model(rank, alpha, dropout, n_last_layers=3):
    from transformers import CLIPModel, CLIPProcessor
    from peft import LoraConfig, get_peft_model

    base = CLIPModel.from_pretrained(CHECKPOINT)
    processor = CLIPProcessor.from_pretrained(CHECKPOINT)

    n_vision = len(base.vision_model.encoder.layers)
    n_text = len(base.text_model.encoder.layers)
    targets = []
    for i in range(max(0, n_vision - n_last_layers), n_vision):
        targets += [f"vision_model.encoder.layers.{i}.self_attn.q_proj",
                    f"vision_model.encoder.layers.{i}.self_attn.v_proj"]
    for i in range(max(0, n_text - n_last_layers), n_text):
        targets += [f"text_model.encoder.layers.{i}.self_attn.q_proj",
                    f"text_model.encoder.layers.{i}.self_attn.v_proj"]

    lora_cfg = LoraConfig(
        r=rank, lora_alpha=alpha, lora_dropout=dropout,
        target_modules=targets, bias="none",
    )
    model = get_peft_model(base, lora_cfg)
    model.to(device)
    return model, processor


# ── Losses ────────────────────────────────────────────────────────────────

def supcon_loss(features, labels, temperature):
    """Standard multi-positive supervised contrastive loss (Khosla et al.)."""
    features = F.normalize(features, dim=-1)
    sim = features @ features.T / temperature
    n = sim.shape[0]
    mask_self = torch.eye(n, dtype=torch.bool, device=sim.device)
    sim = sim.masked_fill(mask_self, -1e9)

    labels_t = torch.tensor(labels, device=sim.device)
    pos_mask = (labels_t.unsqueeze(0) == labels_t.unsqueeze(1)) & ~mask_self

    log_prob = sim - torch.logsumexp(sim, dim=1, keepdim=True)
    n_pos = pos_mask.sum(dim=1)
    has_pos = n_pos > 0
    if has_pos.sum() == 0:
        return torch.tensor(0.0, device=sim.device, requires_grad=True)
    loss = -(pos_mask * log_prob).sum(dim=1)[has_pos] / n_pos[has_pos].clamp(min=1)
    return loss.mean()


def image_text_infonce(img_feats, label_ids, text_feats_by_label, temperature):
    """Multi-positive image->text InfoNCE: positives are all text prompts
    whose label matches the image's label (here just 1 per label, but the
    loss handles multiple positives generically)."""
    img_feats = F.normalize(img_feats, dim=-1)
    unique_labels = list(text_feats_by_label.keys())
    text_bank = F.normalize(torch.stack([text_feats_by_label[l] for l in unique_labels]), dim=-1)
    sim = img_feats @ text_bank.T / temperature  # [batch, n_unique_labels]
    label_to_idx = {l: i for i, l in enumerate(unique_labels)}
    targets = torch.tensor([label_to_idx[l] for l in label_ids], device=sim.device)
    return F.cross_entropy(sim, targets)


def _as_tensor(features):
    """CLIPModel.get_{text,image}_features returns a plain tensor on some
    transformers versions and a BaseModelOutputWithPooling (projected
    features in .pooler_output) on others. Normalize to a plain tensor."""
    if torch.is_tensor(features):
        return features
    return features.pooler_output


def compute_batch_loss(model, processor, pixel_values, labels, temperature, text_weight):
    pixel_values = pixel_values.to(device)
    img_feats = _as_tensor(model.get_image_features(pixel_values=pixel_values))

    unique_labels = sorted(set(labels))
    prompts = [LABEL_TO_PROMPT[l] for l in unique_labels]
    text_inputs = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
    text_inputs = {k: v.to(device) for k, v in text_inputs.items()}
    text_feats = _as_tensor(model.get_text_features(**text_inputs))
    text_feats_by_label = {l: text_feats[i] for i, l in enumerate(unique_labels)}

    label_ids = [hash(l) % (2**31) for l in labels]  # stable int ids for supcon
    loss_img = supcon_loss(img_feats, label_ids, temperature)
    loss_txt = image_text_infonce(img_feats, labels, text_feats_by_label, temperature)
    return loss_img + text_weight * loss_txt


# ── Training loop ─────────────────────────────────────────────────────────

def train_run(hparams, train_files, train_labels, val_files, val_labels,
              max_epochs=8, patience=2, verbose=True):
    torch.manual_seed(0)
    model, processor = build_lora_model(hparams["lora_rank"], hparams["lora_alpha"], hparams["lora_dropout"])
    model.train()

    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=hparams["lr"], weight_decay=hparams["weight_decay"])

    train_ds = FashionDataset(train_files, train_labels, augment=True)
    val_ds = FashionDataset(val_files, val_labels, augment=False)
    bs = hparams["batch_size"]
    train_loader = DataLoader(train_ds, batch_size=bs, shuffle=True,
                               collate_fn=lambda b: collate(b, processor), drop_last=len(train_ds) > bs)
    val_loader = DataLoader(val_ds, batch_size=bs, shuffle=False,
                             collate_fn=lambda b: collate(b, processor))

    best_val = float("inf")
    best_state = None
    epochs_no_improve = 0

    for epoch in range(max_epochs):
        model.train()
        train_losses = []
        for pixel_values, labels in train_loader:
            optimizer.zero_grad()
            loss = compute_batch_loss(model, processor, pixel_values, labels,
                                       hparams["temperature"], hparams["text_loss_weight"])
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        val_losses = []
        with torch.no_grad():
            for pixel_values, labels in val_loader:
                loss = compute_batch_loss(model, processor, pixel_values, labels,
                                           hparams["temperature"], hparams["text_loss_weight"])
                val_losses.append(loss.item())
        train_loss = float(np.mean(train_losses)) if train_losses else float("nan")
        val_loss = float(np.mean(val_losses)) if val_losses else float("nan")
        if verbose:
            print(f"  epoch {epoch+1}/{max_epochs}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}")

        if val_loss < best_val - 1e-4:
            best_val = val_loss
            epochs_no_improve = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items() if "lora" in k}
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                if verbose:
                    print(f"  early stopping at epoch {epoch+1} (best val_loss={best_val:.4f})")
                break

    if best_state is not None:
        model.load_state_dict(best_state, strict=False)
    return model, processor, best_val


# ── k-fold CV objective for Optuna ──────────────────────────────────────

def kfold_objective(hparams, rows_by_label, k=3, max_epochs=3, patience=1):
    """Stratified k-fold CV over the train split only; returns mean best val loss."""
    fold_assign = {}
    rng = random.Random(123)
    for label, files in rows_by_label.items():
        files = files[:]
        rng.shuffle(files)
        for i, f in enumerate(files):
            fold_assign[f] = i % k

    losses = []
    all_files = list(fold_assign.keys())
    for fold in range(k):
        val_f = [f for f in all_files if fold_assign[f] == fold]
        train_f = [f for f in all_files if fold_assign[f] != fold]
        if len(val_f) == 0 or len(train_f) == 0:
            continue
        lm = label_map()
        train_labels = [lm[f] for f in train_f]
        val_labels = [lm[f] for f in val_f]
        _, _, val_loss = train_run(hparams, train_f, train_labels, val_f, val_labels,
                                    max_epochs=max_epochs, patience=patience, verbose=False)
        losses.append(val_loss)
    return float(np.mean(losses)) if losses else float("inf")


def run_optuna(n_trials):
    import optuna

    train_files, val_files, _ = get_splits()
    lm = label_map()
    rows_by_label = {}
    for f in train_files:
        rows_by_label.setdefault(lm[f], []).append(f)

    def objective(trial):
        hparams = {
            "lora_rank": trial.suggest_categorical("lora_rank", [4, 8]),
            "lora_alpha": trial.suggest_categorical("lora_alpha", [8, 16, 32]),
            "lora_dropout": trial.suggest_float("lora_dropout", 0.0, 0.3),
            "lr": trial.suggest_float("lr", 1e-5, 5e-4, log=True),
            "weight_decay": trial.suggest_float("weight_decay", 1e-4, 0.1, log=True),
            "temperature": trial.suggest_float("temperature", 0.03, 0.2),
            "batch_size": trial.suggest_categorical("batch_size", [8, 16]),
            "text_loss_weight": trial.suggest_float("text_loss_weight", 0.1, 1.0),
        }
        t0 = time.time()
        val = kfold_objective(hparams, rows_by_label, k=3, max_epochs=3, patience=1)
        print(f"trial {trial.number}: val_loss={val:.4f} ({time.time()-t0:.1f}s) params={hparams}")
        return val

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=42))
    t_start = time.time()
    study.optimize(objective, n_trials=n_trials)
    print(f"Optuna sweep of {n_trials} trials took {time.time()-t_start:.1f}s total")
    print("Best params:", study.best_params)
    print("Best val_loss:", study.best_value)

    best = dict(DEFAULT_HPARAMS)
    best.update(study.best_params)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BEST_HPARAMS_FILE, "w") as f:
        json.dump({"best_params": best, "best_val_loss": study.best_value,
                   "n_trials": n_trials}, f, indent=2)
    print(f"Saved best hyperparameters to {BEST_HPARAMS_FILE}")


def run_final_training(max_epochs=10, patience=3):
    if os.path.exists(BEST_HPARAMS_FILE):
        with open(BEST_HPARAMS_FILE) as f:
            hparams = json.load(f)["best_params"]
        print(f"Using Optuna-tuned hyperparameters from {BEST_HPARAMS_FILE}")
    else:
        hparams = DEFAULT_HPARAMS
        print("No Optuna results found; using default hyperparameters")
    print("Hyperparameters:", hparams)

    train_files, val_files, _ = get_splits()
    lm = label_map()
    train_labels = [lm[f] for f in train_files]
    val_labels = [lm[f] for f in val_files]

    t0 = time.time()
    model, processor, best_val = train_run(hparams, train_files, train_labels, val_files, val_labels,
                                            max_epochs=max_epochs, patience=patience, verbose=True)
    print(f"Final training took {time.time()-t0:.1f}s, best val_loss={best_val:.4f}")

    os.makedirs(ADAPTER_DIR, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    print(f"Saved LoRA adapter to {ADAPTER_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--optuna", type=int, default=0, help="number of Optuna trials to run")
    parser.add_argument("--train", action="store_true", help="train final adapter")
    parser.add_argument("--max_epochs", type=int, default=10)
    parser.add_argument("--patience", type=int, default=3)
    args = parser.parse_args()

    if args.optuna:
        run_optuna(args.optuna)
    elif args.train:
        run_final_training(max_epochs=args.max_epochs, patience=args.patience)
    else:
        parser.print_help()
