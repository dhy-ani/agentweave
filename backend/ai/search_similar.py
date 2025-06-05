import faiss
import json
import numpy as np
from extract_vector import load_clip_model, load_image, get_clip_vector


def search_similar_images(query_path, k=5):
    # Load FAISS index and filenames
    index = faiss.read_index("datasets/vectors/faiss_index.ivfpq")
    with open("datasets/vectors/index_filenames.json", "r") as f:
        filenames = json.load(f)

    # Load model and query vector
    model, preprocess, _ = load_clip_model()
    image = load_image(query_path)
    vector = get_clip_vector(image, model, preprocess).astype("float32").reshape(1, -1)

    # Search
    index.nprobe = 8
    distances, indices = index.search(vector, k)

    # Show results
    print(f"\nTop {k} similar images to {query_path}:")
    for i in indices[0]:
        print(filenames[i])


if __name__ == "__main__":
    search_similar_images("test/test_images/summer.jpg", k=5)
