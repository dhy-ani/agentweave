import json 
import numpy as np


def load_vectors(json_path):
    with open(json_path, "r") as f:
        vectors = json.load(f)
        
    filenames = list(vectors.keys())
    vectors_array = np.array([vectors[filename]["vector"] for filename in filenames])
    return filenames, vectors_array



#KMeans
from collections import defaultdict
import json
from sklearn.cluster import KMeans


if __name__ == "__main__":
    json_path = "datasets/vectors/blip_clip_combined.json"
    filenames, vectors_array = load_vectors(json_path)
    print(f"Loaded {len(filenames)} vectors. First vector shape: {vectors_array[0].shape}")

        
    kmeans = KMeans(n_clusters= 8, random_state=42)
    labels = kmeans.fit_predict(vectors_array)
    # Group filenames by their cluster labels
    cluster_map = {}
    for filename, label in zip(filenames, labels):
        if label not in cluster_map:
            cluster_map[int(label)] = []
        cluster_map[int(label)].append(filename)
    # Save the cluster mapping to a JSON file
    output_path = "datasets/vectors/cluster_map.json"
    with open(output_path, "w") as f:
        json.dump(cluster_map, f, indent=2)

    print(f"Cluster map saved to {output_path}")



    cluster_groups = defaultdict(list)
    for filename, label in cluster_map.items():
        cluster_groups[str(label)].append(filename)

    # Save grouped filenames (by cluster)
    with open("datasets/vectors/cluster_groups.json", "w") as f:
        json.dump(cluster_groups, f, indent=2)
    print("Saved cluster_groups.json")