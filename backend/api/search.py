"""Similar-medicine vector search HTTP routes."""

from __future__ import annotations

from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.deps import require_roles
from backend.core.roles import STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.search import SearchRequest, SearchResult
from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_search import search_similar_medicines

router = APIRouter()


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def _is_same_medicine(query: str, candidate: str) -> bool:
    """Treat exact / near-exact names (incl. common typos) as the same drug."""
    q, c = _normalize(query), _normalize(candidate)
    if not q or not c:
        return False
    if q == c:
        return True
    if abs(len(q) - len(c)) <= 2 and (q in c or c in q):
        return True
    return SequenceMatcher(None, q, c).ratio() >= 0.85


def _query_text_for_search(medicine_name: str) -> str:
    """Prefer drug-summary text for embeddings; fall back to the typed name."""
    name = medicine_name.strip()
    if not name:
        return ""
    summary = fetch_drug_summary(name)
    if summary and summary != "No data found.":
        return summary
    return name


def _inventory_name_fallback(
    db: Session, query: str, top_k: int, exclude_query: str
) -> list[SearchResult]:
    """When vector search has no hits, suggest other in-stock names by fuzzy match."""
    q_norm = _normalize(query)
    if not q_norm:
        return []
    rows = db.query(models.Medicine).filter(models.Medicine.quantity > 0).all()
    scored: list[tuple[float, models.Medicine]] = []
    for med in rows:
        if _is_same_medicine(exclude_query, med.name):
            continue
        ratio = SequenceMatcher(None, q_norm, _normalize(med.name)).ratio()
        if ratio >= 0.45:
            scored.append((ratio, med))
    scored.sort(key=lambda t: (-t[0], t[1].name.lower()))
    out: list[SearchResult] = []
    for ratio, med in scored[:top_k]:
        out.append(
            SearchResult(
                name=med.name,
                score=1.0 - ratio,
                quantity=med.quantity,
            )
        )
    return out


@router.post("/similar", response_model=list[SearchResult])
def find_similar(
    request: SearchRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Find **other** in-stock inventory medicines similar to ``medicine_name``.

    Results are intersected with current inventory (quantity > 0) and never
    include the queried medicine itself.
    """
    query_text = _query_text_for_search(request.medicine_name)
    if not query_text:
        raise HTTPException(status_code=400, detail="medicine_name is required")

    # Over-fetch so we still have enough after inventory / self filters.
    fetch_k = min(50, max(request.top_k * 5, 20))
    raw = search_similar_medicines(query_text=query_text, top_k=fetch_k)

    in_stock = {
        m.name: m
        for m in db.query(models.Medicine).filter(models.Medicine.quantity > 0).all()
    }
    by_lower = {name.lower(): med for name, med in in_stock.items()}

    results: list[SearchResult] = []
    seen: set[str] = set()
    for hit in raw:
        hit_name = (hit.get("name") or "").strip()
        if not hit_name:
            continue
        if _is_same_medicine(request.medicine_name, hit_name):
            continue
        med = by_lower.get(hit_name.lower())
        if med is None:
            continue
        key = med.name.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            SearchResult(
                name=med.name,
                score=float(hit["score"]),
                quantity=med.quantity,
            )
        )
        if len(results) >= request.top_k:
            break

    if not results:
        results = _inventory_name_fallback(
            db, request.medicine_name, request.top_k, request.medicine_name
        )

    return results
