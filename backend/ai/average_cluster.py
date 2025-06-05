import json
import numpy as np


with open("datasets/vectors/blip_clip_combined.json", "r") as f:
    data = json.load(f)

with open("datasets/vectors/cluster_map.json", "r") as f:
    cluster_map = json.load(f)
    
trend_vectors = {}
for cluster_id, filenames in cluster_map.items():
    vectors =[]
    captions = []
    for filename in filenames:
        if filename in data:
            vectors.append(data[filename]["vector"])
            captions.append(data[filename]["caption"])
            
    if vectors:
        avg_vector = np.mean(vectors, axis=0).tolist()
        trend_vectors[cluster_id] = {
            "vector": avg_vector,
            "captions": captions
        }
        
with open("datasets/vectors/trend_vectors.json", "w") as f:
    json.dump(trend_vectors, f, indent=2)

print("Saved trend vectors to datasets/vectors/trend_vectors.json")
