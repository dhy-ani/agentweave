from fastapi import FastAPI, Request

app = FastAPI()



from fastapi.middleware.cors import CORSMiddleware
from routers import user, stylegenie 

from fastapi.staticfiles import StaticFiles
import os
from routers.stylegenie import router as stylegenie_router
from routers.analyze_body import router as analyze_body_router

app.include_router(analyze_body_router)

app.include_router(stylegenie_router)

app.include_router(user.router)
app.include_router(stylegenie.router)  



# # Get absolute path to datasets/rawImages
static_image_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "rawImages"))

# Ensure the path exists
if not os.path.isdir(static_image_dir):
    raise RuntimeError(f"Static image directory not found: {static_image_dir}")

# Mount it
app.mount("/images", StaticFiles(directory=static_image_dir), name="images")

# CORS allows frontend to call backend from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"➡️ Incoming: {request.method} {request.url}")
    response = await call_next(request)
    return response

@app.get("/")
def read_root():
    return {"status": "StyleGenie backend is running ✅"}




