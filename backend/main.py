"""PharmaAssist FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import inventory, ocr_api, search
from backend.core.config import get_cors_origins

app = FastAPI(
    title="PharmaAssist Backend",
    description="Pharmacy inventory, vector search, and prescription OCR APIs.",
)

_cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Credentials cannot be combined with wildcard origins in browsers.
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(search.router, prefix="/search", tags=["Vector Search"])
app.include_router(ocr_api.router, prefix="/ocr", tags=["OCR"])


@app.get("/")
def read_root():
    """Liveness check for the API process."""
    return {"message": "PharmaAssist API is running."}
