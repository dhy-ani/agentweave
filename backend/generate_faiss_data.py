import os
import json
import numpy as np
import faiss
from tqdm import tqdm
from datetime import datetime
from ai.extract_vector import extract_image_vector
from ai.caption_images import merge_clip_with_captions  # Optional, if you have BLIP setup

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "datasets", "rawImages"))
OUTPUT_DIR = os.path.join(BASE_DIR, "ai", "data")



# Output files
VECTOR_FILE = os.path.join(OUTPUT_DIR, "image_vectors.npy")
CAPTION_FILE = os.path.join(OUTPUT_DIR, "index_to_caption.json")
IMAGE_PATH_FILE = os.path.join(OUTPUT_DIR, "index_to_image_path.json")
INDEX_FILE = os.path.join(OUTPUT_DIR, "trends.index")
TIMESTAMP_FILE = os.path.join(OUTPUT_DIR, "index_to_timestamp.json")


vectors = []
index_to_caption = {}
index_to_image_path = {}
index_to_timestamp = {}  # ← New dictionary

for idx, filename in enumerate(tqdm(os.listdir(IMAGE_DIR))):
    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        path = os.path.join(IMAGE_DIR, filename)

        vec = extract_image_vector(path)
        vectors.append(vec)

        caption = merge_clip_with_captions(path) if os.path.exists("ai/caption_images.py") else f"Outfit from {filename}"

        index_to_caption[str(idx)] = caption
        index_to_image_path[str(idx)] = path
        index_to_timestamp[str(idx)] = datetime.now().isoformat()

# Save all vectors and metadata
np.save(VECTOR_FILE, np.array(vectors))

with open(CAPTION_FILE, "w") as f:
    json.dump(index_to_caption, f, indent=2)

with open(IMAGE_PATH_FILE, "w") as f:
    json.dump(index_to_image_path, f, indent=2)
    
with open(TIMESTAMP_FILE, "w") as f:
    json.dump(index_to_timestamp, f, indent=2)



# Build FAISS index
dim = 512
index = faiss.IndexFlatL2(dim)
index.add(np.array(vectors))
faiss.write_index(index, INDEX_FILE)

print(" All files generated successfully.")
