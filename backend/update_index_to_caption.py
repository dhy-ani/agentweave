import json
import os 
# Paths to relevant files
blip_clip_path = "../datasets/vectors/blip_clip_combined.json"
index_to_image_path = "ai/data/index_to_image_path.json"
output_caption_path = "ai/data/index_to_caption.json"

# Load BLIP+CLIP data
with open(blip_clip_path) as f:
    caption_data = json.load(f)

# Load FAISS index-to-image mapping
with open(index_to_image_path) as f:
    idx_to_image = json.load(f)

# Build updated index-to-caption map
index_to_caption = {}

for idx, filename in idx_to_image.items():
    key = os.path.basename(filename.strip())
  # remove whitespace just in case
    if key in caption_data:
        index_to_caption[idx] = caption_data[key]["caption"]
    else:
        index_to_caption[idx] = "No caption available."

# Save new index-to-caption file
with open(output_caption_path, "w") as f:
    json.dump(index_to_caption, f, indent=2)

print("✅ index_to_caption.json updated with BLIP-generated captions.")
