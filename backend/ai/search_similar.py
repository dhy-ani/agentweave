import faiss
import json
import numpy as np
from extract_vector import load_clip_model, load_image, get_clip_vector

def search_similar_images(query_path, k=5):
    index = faiss.read_index("datasets/vectors/faiss_index.ivfpq")
    with open("datasets/vectors/index_filenames.json", "r") as f:
        filenames = json.load(f)

    model, preprocess = load_clip_model()
    image = load_image(query_path)
    vector = get_clip_vector(image, model, preprocess).astype("float32").reshape(1, -1)

    index.nprobe = 8
    distances, indices = index.search(vector, k)

    print(f"\n🔍 Top {k} similar images to {query_path}:")
    for i, dist in zip(indices[0], distances[0]):
        print(f"📸 {filenames[i]} (distance: {dist:.3f})")


if __name__ == "__main__":
    search_similar_images("test/summer.jpg", k=5)
