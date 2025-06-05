import open_clip as oc

import torch
from PIL import Image #load images
import numpy as np

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
    
    