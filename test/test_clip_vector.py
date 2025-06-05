# test/test_clip_vector.py
import os 
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai.trend_radar import load_clip_model, load_image, get_clip_vector

model, preprocess, _ = load_clip_model()
image = load_image("test/test_images/testimage.png")  # Make sure this image exists
vector = get_clip_vector(image, model, preprocess)

print("Vector shape:", vector.shape)
print("Vector preview:", vector[:5])
