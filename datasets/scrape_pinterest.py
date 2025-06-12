from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import requests
from PIL import Image
from io import BytesIO
from tqdm import tqdm

search_queries = [
    "techwear outfit for men",
    "minimalist neutral-toned outfit",
    "retro summer streetwear",
    "business casual fashion for women",
    "cottagecore dress with lace",
    "Korean street fashion for teens",
    "boho beach vacation outfit",
    "quiet luxury men's suit",
    "Y2K pastel top and skirt",
    "plus-size fashion formal look",
    "monochrome oversized blazer outfit",
    "Indian ethnic wear for weddings",
    "athleisure gym outfit",
    "modest fashion hijab style",
    "preppy school outfit for fall",
    "grunge punk look with leather",
    "layered fall outfit with scarf",
    "rainy day functional fashion",
    "evening gown for red carpet",
    "denim-on-denim casual combo",
    "vintage 90s skatewear",
    "gender-neutral streetwear",
    "summer festival look with glitter",
    "officewear outfit for short women"
]


options = webdriver.ChromeOptions()
options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

for query in search_queries:
    url =f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    driver.get(url)
    time.sleep(3)  # Wait for the page to load
    
    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

    # RELOAD image elements after scrolling is done to avoid going to a new page without downloading images
    time.sleep(2)
    image_elements = driver.find_elements("tag name", "img")

    img_urls = []
    for img in image_elements:
        try:
            src = img.get_attribute("src")
            if src and "http" in src and not src.startswith("data:"):
                img_urls.append(src)
        except Exception as e:
            print("Skipping stale image:", e)
            continue

    print(f"Found {len(img_urls)} image URLs for '{query}'")

    # Filter out None or empty URLs
    image_urls = list(filter(None, img_urls))     

    # Remove duplicates
    image_urls = list(set(image_urls))  



    for i, img_url in enumerate(tqdm(img_urls[:20])):
        try:
            response = requests.get(img_url, timeout=10)
            img = Image.open(BytesIO(response.content)).convert("RGB")
            filename = f"{query[:10].replace(' ', '_')}_{i}.jpg"
            # Download images
            save_dir = os.path.join("datasets", "rawImages")
            os.makedirs(save_dir, exist_ok=True)
            img.save(os.path.join(save_dir, filename))
        except Exception as e:
            print(f"Failed to save image {i}: {e}")

    
# Close the driver
driver.quit()