"""Similar-medicine vector search HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.schemas.search import SearchRequest, SearchResult
from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_search import search_similar_medicines

router = APIRouter()


@router.post("/similar", response_model=list[SearchResult])
def find_similar(request: SearchRequest):
    """Find inventory medicines whose embeddings are close to ``medicine_name``."""
    summary = fetch_drug_summary(request.medicine_name)
    if not summary or summary == "No data found.":
        raise HTTPException(status_code=404, detail="Summary not found for the requested medicine")
    results = search_similar_medicines(query_text=summary, top_k=request.top_k)
    return results
