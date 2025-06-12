import os
import json
import torch
from PIL import Image, UnidentifiedImageError
from transformers import BlipProcessor, BlipForConditionalGeneration
from tqdm import tqdm

def load_blip_model(device="cpu"):
    """Load BLIP model and processor."""
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    model.to(device)
    model.eval()
    return model, processor

def load_image(image_path):
    """Safely load and convert image to RGB."""
    try:
        return Image.open(image_path).convert("RGB")
    except UnidentifiedImageError:
        raise ValueError(f"Invalid image file: {image_path}")

def generate_caption(image, model, processor, device="cpu", max_new_tokens=20):
    """Generate a caption using BLIP for a given image."""
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens)
    return processor.decode(out[0], skip_special_tokens=True).strip()

def merge_clip_with_captions(image_dir, clip_vector_path, output_path, device="cpu"):
    """Merge image captions from BLIP with existing CLIP vectors."""
    print("🔄 Loading BLIP model...")
    blip_model, blip_processor = load_blip_model(device)

    print("📂 Loading CLIP vector file...")
    with open(clip_vector_path, "r") as f:
        clip_data = json.load(f)

    combined_data = {}

    print("🖼️ Processing images and generating captions...")
    for img_name, vector in tqdm(clip_data.items(), total=len(clip_data)):
        image_path = os.path.join(image_dir, img_name)
        if not os.path.isfile(image_path):
            print(f"⚠️ Skipped missing file: {img_name}")
            continue

        try:
            image = load_image(image_path)
            caption = generate_caption(image, blip_model, blip_processor, device=device)
            if not caption or caption.isspace():
                caption = "No caption generated."

            combined_data[img_name] = {
                "caption": caption,
                "vector": vector
            }

        except Exception as e:
            print(f"❌ Error with {img_name}: {str(e)}")

    print(f"💾 Saving combined data to {output_path}")
    with open(output_path, "w") as f:
        json.dump(combined_data, f, indent=2)

    print(f"✅ Done! {len(combined_data)} entries saved.")

# Run the script
if __name__ == "__main__":
    image_folder = "datasets/rawImages"
    vector_file = "datasets/vectors/clip_vectors.json"
    output_file = "datasets/vectors/blip_clip_combined.json"
    device = "cuda" if torch.cuda.is_available() else "cpu"

    merge_clip_with_captions(image_folder, vector_file, output_file, device)


# import os
# import json
# from PIL import Image
# from transformers import BlipProcessor, BlipForConditionalGeneration
# import torch

# # Load BLIP
# def load_blip_model():
#     processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
#     model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
#     model.eval()
#     return model, processor

# def load_image(image_path):
#     return Image.open(image_path).convert("RGB")

# def generate_caption(image, model, processor):
#     inputs = processor(images=image, return_tensors="pt")
#     with torch.no_grad():
#         out = model.generate(**inputs)
#     return processor.decode(out[0], skip_special_tokens=True)

# def merge_clip_with_captions(image_dir, clip_vector_path, output_path):
#     blip_model, blip_processor = load_blip_model()

#     with open(clip_vector_path, "r") as f:
#         clip_data = json.load(f)

#     combined_data = {}

#     for img_name, vector in clip_data.items():
#         image_path = os.path.join(image_dir, img_name)
#         if not os.path.isfile(image_path):
#             print(f"Skipped {img_name} (missing file)")
#             continue

#         try:
#             image = load_image(image_path)
#             caption = generate_caption(image, blip_model, blip_processor)
#             combined_data[img_name] = {
#                 "caption": caption,
#                 "vector": vector
#             }
#             print(f"{img_name}: {caption}")
#         except Exception as e:
#             print(f"Error with {img_name}: {e}")

#     with open(output_path, "w") as f:
#         json.dump(combined_data, f, indent=2)
#     print(f"\nCombined data saved to: {output_path}")

# # Run
# if __name__ == "__main__":
#     image_folder = "datasets/rawImages"
#     vector_file = "datasets/vectors/clip_vectors.json"
#     output_file = "datasets/vectors/blip_clip_combined.json"
#     merge_clip_with_captions(image_folder, vector_file, output_file)
