import open_clip as oc
import torch
from PIL import Image, UnidentifiedImageError
import numpy as np
import os
import json
import clip  # ✅ Keeping OpenAI's clip for text vectors

# Setup device
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load OpenCLIP model (for image)
def load_clip_model():
    model, _, preprocess = oc.create_model_and_transforms(
        "ViT-B-32",
        pretrained="laion400m_e32",
        device=device
    )
    model.eval()
    return model, preprocess

# -----------------------------
# Image vectorization functions
# -----------------------------

def load_image(image_path: str) -> Image.Image:
    return Image.open(image_path).convert("RGB")

def get_clip_vector(image: Image.Image, model, preprocess) -> np.ndarray:
    image_input = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        image_features = model.encode_image(image_input)
        image_features /= image_features.norm(dim=-1, keepdim=True)
    return image_features.cpu().numpy().flatten()

def extract_image_vector(image_path: str, model=None, preprocess=None) -> np.ndarray:
    try:
        image = load_image(image_path)
        model = model or load_clip_model()[0]
        preprocess = preprocess or load_clip_model()[1]
        return get_clip_vector(image, model, preprocess)
    except UnidentifiedImageError:
        raise ValueError("Invalid image file")
    except Exception as e:
        raise RuntimeError(f"Failed to extract image vector: {str(e)}")

# -----------------------------
# Text vectorization (OpenAI CLIP)
# -----------------------------

def extract_text_vector(prompt: str) -> np.ndarray:
    model, preprocess = clip.load("ViT-B/32", device=device)
    tokens = clip.tokenize([prompt]).to(device)
    with torch.no_grad():
        text_features = model.encode_text(tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)
    return text_features.cpu().numpy().flatten()

# -----------------------------
# Batch extraction
# -----------------------------

def extract_all_clip_vectors(image_dir: str, output_path: str):
    model, preprocess = load_clip_model()
    vectors_dict = {}
    for image_name in os.listdir(image_dir):
        image_path = os.path.join(image_dir, image_name)
        if os.path.isfile(image_path) and image_name.lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                vector = get_clip_vector(load_image(image_path), model, preprocess)
                vectors_dict[image_name] = vector.tolist()
                print(f"✅ Processed: {image_name}")
            except Exception as e:
                print(f"❌ Skipped {image_name}: {e}")

    with open(output_path, "w") as f:
        json.dump(vectors_dict, f, indent=2)

    print(f"\n✅ Saved all vectors to: {output_path}")

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    image_dir = "datasets/rawImages"
    output_path = "datasets/vectors/clip_vectors.json"
    extract_all_clip_vectors(image_dir, output_path)
