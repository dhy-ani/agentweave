import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Load trend vectors (already clustered and averaged)
with open("datasets/vectors/trend_vectors.json", "r") as f:
    trend_vectors_dict = json.load(f)

trend_ids = list(trend_vectors_dict.keys())
vectors = [trend_vectors_dict[tid]["vector"] for tid in trend_ids]
captions = [trend_vectors_dict[tid]["captions"][0] for tid in trend_ids]

# Convert vectors to NumPy array for similarity search
trend_vectors = np.array(vectors)

def recommend_trend(input_vector, top_k=1):
    input_vector = np.array(input_vector).reshape(1, -1)  # (1, 512)
    similarities = cosine_similarity(input_vector, trend_vectors)[0]
    top_indices = np.argsort(similarities)[::-1][:top_k]

    recommendations = []
    for idx in top_indices:
        recommendations.append({
            "cluster": trend_ids[idx],
            "sample_caption": captions[idx],
            "similarity": float(similarities[idx])
        })
    return recommendations

if __name__ == "__main__":
    from extract_vector import load_clip_model, load_image, get_clip_vector

    model, preprocess, _ = load_clip_model()
    image = load_image("test/test_images/summer.jpg")
    vector = get_clip_vector(image, model, preprocess)

    results = recommend_trend(vector)
    for res in results:
        print(f"\nRecommended Cluster: {res['cluster']}")
        print(f"Sample Caption: {res['sample_caption']}")
        print(f"Similarity Score: {res['similarity']:.4f}")
