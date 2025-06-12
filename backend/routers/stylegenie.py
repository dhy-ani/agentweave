from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import sys
import faiss
import numpy as np
import json
from datetime import datetime
import random
from PIL import Image, UnidentifiedImageError
import io
import torchvision.transforms as transforms
import torch

# Fix path to import custom modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai.extract_vector import extract_text_vector

router = APIRouter(prefix="/stylegenie", tags=["StyleGenie"])

# -------------------------------
# Pydantic Models
# -------------------------------

class StyleRequest(BaseModel):
    weather: str
    occasion: str
    location: str
    occupation: str
    relevance: Optional[str] = "current"

class TrendPrompt(BaseModel):
    prompt: str

# -------------------------------
# Load FAISS Index & Metadata
# -------------------------------

try:
    faiss_index = faiss.read_index("ai/data/trends.index")

    with open("ai/data/index_to_caption.json") as f:
        index_to_caption = json.load(f)
    with open("ai/data/index_to_image_path.json") as f:
        index_to_image_path = json.load(f)
    with open("ai/data/index_to_timestamp.json") as f:
        index_to_timestamp = json.load(f)
except Exception as e:
    raise RuntimeError(f"Failed to load FAISS index or metadata: {e}")

# -------------------------------
# Trend-Based Recommendation
# -------------------------------

@router.post("/trend_vector")
async def recommend_outfit(data: TrendPrompt):
    try:
        prompt = data.prompt
        if isinstance(prompt, list):
            prompt = " ".join(prompt)
        print("📨 Prompt received:", data.prompt)
        
        # 1. Vectorize prompt
        vector = extract_text_vector(data.prompt)
        vector = np.array(vector).flatten().astype(np.float32).reshape(1, -1)

        # 2. FAISS search
        D, I = faiss_index.search(vector, k=10)
        print("🔍 FAISS search done. Distances:", D)
        
        
        # 3. Prepare response fields
        top_index = str(I[0][0])
        image_path = index_to_image_path.get(top_index)
        if not image_path:
            raise HTTPException(status_code=500, detail=f"No image path found for index {top_index}")

        filename = os.path.basename(image_path)

        image_url = filename

        outfit = index_to_caption[top_index]

        # 4. Trendiness Score Calculation (timestamp-based)
        timestamps = [
            datetime.fromisoformat(index_to_timestamp[str(i)])
            for i in I[0] if str(i) in index_to_timestamp
        ]
        
        print("🕒 Found timestamps for:", len(timestamps))
        now = datetime.now()
        recencies = [(now - ts).days for ts in timestamps]

        def compute_trendiness_score(avg_days, scale=20):
            score = 100 * np.exp(-avg_days / scale)
            return round(score, 1)

        if recencies:
            avg_days = np.mean(recencies)
            trendiness_score = compute_trendiness_score(avg_days)
        else:
            score_raw = float(D[0][0])
            if not np.isfinite(score_raw) or score_raw < 0:
                score_raw = 1.0
            trendiness_score = round(100 * (1 - min(score_raw / 1.0, 1.0)), 1)




        # 5. Projected future trend comment
        future_projection = (
            random.choice([
                "This trend is exploding this season.",
                "This style is gaining popularity.",
                "Expected to stay consistent this quarter."
            ]) if trendiness_score > 60 else
            "This trend might be fading out. Try something else soon!"
        )

        # 6. Return result
        
        results = []
        for idx in I[0][:10]:  # top 10 indices
            idx_str = str(idx)
            filename = os.path.basename(index_to_image_path[idx_str])
            image_url = filename
            outfit = index_to_caption[idx_str]
            
        result = {
            "result": f"Here's a trending look: {outfit}",
             "image": image_url,
            "trendiness_score": trendiness_score,
            "future_projection": future_projection,
            "source": "trend-vector"
        }
        results.append(result)
        
        return { "results": results }
        

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trend vector search failed: {str(e)}")


