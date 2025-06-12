import os
import json
import random
from datetime import datetime, timedelta

# Input directory
IMAGE_PATHS_FILE = "data/index_to_image_path.json"
OUTPUT_FILE = "data/index_to_timestamp.json"

# Load index to image path
with open(IMAGE_PATHS_FILE, "r") as f:
    index_to_path = json.load(f)

index_to_timestamp = {}

# Assign a random timestamp in the past 2 years
for index in index_to_path:
    random_days_ago = random.randint(0, 730)
    date = datetime.now() - timedelta(days=random_days_ago)
    index_to_timestamp[index] = date.strftime("%Y-%m-%d")

# Save to file
with open(OUTPUT_FILE, "w") as f:
    json.dump(index_to_timestamp, f, indent=2)

print(f" index_to_timestamp.json generated with {len(index_to_timestamp)} entries.")
