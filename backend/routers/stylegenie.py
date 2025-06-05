from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
import random
# from openai import OpenAI
# import os
# from dotenv import load_dotenv

from ai.extract_vector import extract_all_clip_vectors
from ai.search_similar import search_similar_images  # or similar function

# load_dotenv()
router = APIRouter(prefix="/stylegenie", tags=["StyleGenie"])

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class StyleRequest(BaseModel):
    weather: str
    occasion: str
    location: str
    occupation: str
    relevance: Optional[str] = "current"

# Simulated outfit database (replace with real logic later)
mock_outfits = {
    "beach": ["Linen shirt + Shorts + Flip-flops", "Tank top + Swim trunks + Sunglasses"],
    "formal": ["Navy suit + White shirt + Oxfords", "Blazer + Slacks + Loafers"],
    "casual": ["Graphic tee + Jeans + Sneakers", "T-shirt + Chinos"],
    "party": ["Silk blouse + Mini skirt + Heels", "Floral dress + Sandals"],
    "office": ["Button-up + Trousers + Derbies", "Knit polo + Chinos"],
    "rainy": ["Raincoat + Umbrella + Waterproof boots"],
    "cold": ["Sweater + Wool coat + Boots", "Thermal shirt + Parka + Beanie"],
    "hot": ["Sleeveless top + Shorts + Sandals", "Crop top + Linen pants"],
    "sunny": ["Wrap dress + Sunglasses + Sandals", "Shorts + Printed shirt + Hat"]
}

import faiss
import numpy as np
import json

# Load FAISS index (or import a function that does it)
faiss_index = faiss.read_index("backend/ai/data/trends.index")  # adjust path

# Load mapping files
with open("backend/ai/data/index_to_caption.json") as f:
    index_to_caption = json.load(f)

with open("backend/ai/data/index_to_image_path.json") as f:
    index_to_image_path = json.load(f)

@router.post("/trend_vector")
async def recommend_outfit(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")

    # Convert to CLIP vector
    vector = extract_all_clip_vectors(prompt)

    # Search FAISS
    D, I = faiss_index.search(np.array([vector]), k=1)
    top_index = str(I[0][0])

    outfit = index_to_caption[top_index]
    image_url = index_to_image_path[top_index]

    return {
        "result": f"Here's a trending look: {outfit}",
        "image": image_url,
        "trendiness_score": round(random.uniform(0.75, 0.95), 2),
        "future_projection": random.choice([
            "This trend is exploding this season.",
            "This style is gaining popularity.",
            "Expected to stay consistent this quarter."
        ]),
        "source": "trend-vector"
    }

# @router.post("/")
# async def generate_outfit(request: Request):
#     data = await request.json()
#     prompt = data.get("prompt")

#     try:
#         # Attempt OpenAI call
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are StyleGenie, a fashionable outfit recommendation expert."},
#                 {"role": "user", "content": prompt}
#             ]
#         )
#         return {
#             "result": response.choices[0].message.content,
#             "source": "openai"
#         }
#     except Exception as e:
#         # Fallback logic using mock_outfits
#         try:
#             # Extract tags from the parsed data
#             tags = []
#             for key in ["weather", "occasion", "location", "occupation"]:
#                 value = data.get(key, "").lower()
#                 if value in prompt.lower():
#                     tags.append(value)

#             possible_looks = []
#             for tag in tags:
#                 if tag in mock_outfits:
#                     possible_looks.extend(mock_outfits[tag])

#             if not possible_looks:
#                 possible_looks = mock_outfits["casual"]

#             outfit = random.choice(possible_looks)

#             return {
#                 "result": f"GPT is unavailable. Here's a backup outfit suggestion: {outfit}",
#                 "trendiness_score": round(random.uniform(0.6, 0.95), 2),
#                 "future_projection": random.choice([
#                     "This style is gaining popularity.",
#                     "Expected to stay consistent this season.",
#                     "Trend may decline after this quarter."
#                 ]),
#                 "source": "fallback"
#             }
#         except Exception as fallback_error:
#             return {"error": f"OpenAI failed and fallback also failed: {str(fallback_error)}"}
