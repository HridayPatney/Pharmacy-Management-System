"""Similar-medicine vector search HTTP routes."""

from __future__ import annotations

from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.deps import require_roles
from backend.core.roles import INVENTORY_WRITE_ROLES, STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.search import ReindexResponse, SearchRequest, SearchResult
from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_search import search_similar_medicines, vectors_enabled
from backend.services.vector_sync import reindex_all_medicines

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


def _inventory_match(db: Session, medicine_name: str) -> models.Medicine | None:
    """Case-insensitive inventory lookup (any stock level, including zero)."""
    name = medicine_name.strip()
    if not name:
        return None
    return (
        db.query(models.Medicine)
        .filter(func.lower(models.Medicine.name) == name.lower())
        .first()
    )


def _has_stored_embedding(db: Session, medicine_id: str) -> bool:
    """True when Postgres has an embedding row for this inventory id."""
    if not vectors_enabled():
        return False
    return db.get(models.MedicineEmbedding, medicine_id) is not None


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
                medicine_id=med.id,
                name=med.name,
                score=1.0 - ratio,
                quantity=med.quantity,
            )
        )
    return out


@router.post("/reindex", response_model=ReindexResponse)
def reindex_embeddings(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*INVENTORY_WRITE_ROLES)),
):
    """Rebuild pgvector embeddings from every medicine in SQL inventory.

    Use after deploy or when similar-search is empty. Jobs run in the background
    (inline under ``VECTOR_SYNC_INLINE``). No-op storage on SQLite.
    """
    result = reindex_all_medicines(db)
    return ReindexResponse(scheduled=result["scheduled"])


@router.post("/similar", response_model=list[SearchResult])
def find_similar(
    request: SearchRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Find **other** in-stock inventory medicines similar to ``medicine_name``.

    If the queried name matches an inventory row that already has a pgvector
    embedding (including zero/low stock), that stored vector is reused instead
    of fetching a drug summary and re-embedding. Results never include the
    queried medicine itself and require quantity > 0.
    """
    name = request.medicine_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="medicine_name is required")

    matched = _inventory_match(db, name)
    exclude_id = matched.id if matched else None

    # Over-fetch so we still have enough after inventory / self filters.
    fetch_k = min(50, max(request.top_k * 5, 20))

    if matched and _has_stored_embedding(db, matched.id):
        raw = search_similar_medicines(
            query_medicine_id=matched.id,
            top_k=fetch_k,
            exclude_medicine_id=exclude_id,
        )
    else:
        query_text = _query_text_for_search(name)
        if not query_text:
            raise HTTPException(status_code=400, detail="medicine_name is required")
        raw = search_similar_medicines(
            query_text=query_text,
            top_k=fetch_k,
            exclude_medicine_id=exclude_id,
        )

    in_stock = {
        m.name: m
        for m in db.query(models.Medicine).filter(models.Medicine.quantity > 0).all()
    }
    by_lower = {stock_name.lower(): med for stock_name, med in in_stock.items()}

    results: list[SearchResult] = []
    seen: set[str] = set()
    for hit in raw:
        hit_name = (hit.get("name") or "").strip()
        if not hit_name:
            continue
        if _is_same_medicine(name, hit_name):
            continue
        med = by_lower.get(hit_name.lower())
        if med is None:
            continue
        if exclude_id and med.id == exclude_id:
            continue
        key = med.name.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            SearchResult(
                medicine_id=med.id,
                name=med.name,
                score=float(hit["score"]),
                quantity=med.quantity,
            )
        )
        if len(results) >= request.top_k:
            break

    if not results:
        results = _inventory_name_fallback(db, name, request.top_k, name)

    return results
