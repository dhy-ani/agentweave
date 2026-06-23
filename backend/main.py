from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="AgentWeave – StyleGenie Backend")

# CORS must be registered first
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://dhy-ani.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # 1. Create all SQL tables (idempotent — safe to run every boot)
    from db.database import engine, Base
    import db.models  # register all ORM models
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready.")

    # 2. Warm up CLIP models so the first request isn't slow
    try:
        from ai.model_cache import get_text_model, get_image_model
        get_text_model()
        get_image_model()
        print("✅ CLIP models loaded and cached.")
    except Exception as e:
        print(f"⚠️  Model warmup failed: {e}")

# Routers
from routers import user
from routers.stylegenie import router as stylegenie_router
from routers.analyze_body import router as analyze_body_router
from routers.wardrobe import router as wardrobe_router
from routers.shopping import router as shopping_router

app.include_router(analyze_body_router)
app.include_router(stylegenie_router)
app.include_router(user.router)
app.include_router(wardrobe_router)
app.include_router(shopping_router)

# Static file mounts
static_image_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "datasets", "rawImages")
)
if os.path.isdir(static_image_dir):
    app.mount("/images", StaticFiles(directory=static_image_dir), name="images")

wardrobe_upload_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "uploads", "wardrobe")
)
os.makedirs(wardrobe_upload_dir, exist_ok=True)
app.mount("/wardrobe-images", StaticFiles(directory=wardrobe_upload_dir), name="wardrobe-images")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"➡️  {request.method} {request.url.path}")
    return await call_next(request)


@app.get("/")
def read_root():
    return {"status": "StyleGenie backend is running ✅"}
