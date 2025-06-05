import faiss
import numpy as np
import json

# Load your BLIP-CLIP combined vectors
def load_vectors(json_path):
    with open(json_path, "r") as f:
        data = json.load(f)
    filenames = list(data.keys())
    vectors = np.array([data[f]["vector"] for f in filenames]).astype("float32")
    return filenames, vectors

def create_ivfpq_index(vectors, nlist=8, m=4, nbits=4):
    d = vectors.shape[1]  # vector dimension (should be 512)
    quantizer = faiss.IndexFlatL2(d)  # coarse quantizer for IVF
    index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits)
    
    # Train the index (only needed once)
    index.train(vectors)
    index.add(vectors)
    
    return index


def save_index(index, path="datasets/vectors/faiss_index.ivfpq"):
    faiss.write_index(index, path)
    print(f"Index saved to {path}")

def save_filenames(filenames, path="datasets/vectors/index_filenames.json"):
    with open(path, "w") as f:
        json.dump(filenames, f)
    print(f"Filenames saved to {path}")


if __name__ == "__main__":
    json_path = "datasets/vectors/blip_clip_combined.json"
    filenames, vectors = load_vectors(json_path)

    print(f"Loaded {len(filenames)} vectors with shape {vectors.shape}")

    index = create_ivfpq_index(vectors)
    save_index(index)
    save_filenames(filenames)
