from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import user, stylegenie  



app = FastAPI()

app.include_router(user.router)
app.include_router(stylegenie.router)  
# CORS allows frontend to call backend from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return {"message": "pong!"}
