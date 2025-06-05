import open_clip as oc

import torch
from PIL import Image #load images
import numpy as np
import os
import json

#Printing list of models 
#print("Available models:")
#print(oc.pretrained.list_pretrained())

def load_clip_model():
    model, _, preprocess = oc.create_model_and_transforms(
        "ViT-B-32",
        pretrained="laion400m_e32", 
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    
    model.eval()  # Set the model to evaluation mode
    tokenizer = oc.get_tokenizer("ViT-B-32")
    return model, preprocess, tokenizer

def load_image(image_path):
    image = Image.open(image_path).convert("RGB")
    return image

def get_clip_vector(image, model, preprocess):
    image_input = preprocess(image).unsqueeze(0) # add batch dimension
    with torch.no_grad():
        image_features = model.encode_image(image_input)# pass through model
        return image_features.detach().cpu().numpy().flatten() #Extract the vector flatten returns 1D array
    
def extract_all_clip_vectors(image_dir, output_path):
    model, preprocess, _ = load_clip_model()
    vectors_dict = {}

    for image_name in os.listdir(image_dir):
        image_path = os.path.join(image_dir, image_name)
        if os.path.isfile(image_path) and image_name.endswith((".jpg", ".jpeg", ".png")):
            try:
                img = load_image(image_path)
                vector = get_clip_vector(img, model, preprocess)
                vectors_dict[image_name] = vector.tolist()
                print(f"Processed: {image_name}")
            except Exception as e:
                print(f"Skipped {image_name}: {e}")
    
    # Save the result
    with open(output_path, "w") as f:
        json.dump(vectors_dict, f, indent=2)
    print(f"\nSaved all vectors to {output_path}")


if __name__ == "__main__":
    image_dir = "datasets/rawImages"  #  not rawImages
    output_path = "datasets/vectors/clip_vectors.json"
    extract_all_clip_vectors(image_dir, output_path)
