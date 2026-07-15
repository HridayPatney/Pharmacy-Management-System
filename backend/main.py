"""PharmaAssist FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import agent, auth, health, inventory, ocr_api, sales, search
from backend.core.bootstrap import bootstrap_admin_if_needed, ensure_schema
from backend.core.config import get_cors_origins
from backend.core.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create schema and optionally seed the first admin on process start."""
    ensure_schema()
    bootstrap_admin_if_needed()
    yield


app = FastAPI(
    title="PharmaAssist Backend",
    description="Pharmacy inventory, vector search, and prescription OCR APIs.",
    lifespan=lifespan,
)

register_exception_handlers(app)

_cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(sales.router, prefix="/sales", tags=["Sales"])
app.include_router(search.router, prefix="/search", tags=["Vector Search"])
app.include_router(ocr_api.router, prefix="/ocr", tags=["OCR"])
app.include_router(agent.router, prefix="/agent", tags=["Inventory Agent"])


@app.get("/")
def read_root():
    """Liveness check for the API process (compat; prefer ``GET /health/live``)."""
    return {"message": "PharmaAssist API is running."}
