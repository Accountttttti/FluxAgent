from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat import router as chat_router

app = FastAPI(title="FluxAgent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
