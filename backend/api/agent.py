"""Natural-language inventory / sales Q&A (read-only agent)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.deps import require_roles
from backend.core.roles import STAFF_ROLES
from backend.db import models
from backend.db.database import get_db
from backend.schemas.agent import AgentQueryRequest, AgentQueryResponse
from backend.services.inventory_agent import answer_question

router = APIRouter()


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(
    payload: AgentQueryRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Answer an inventory/sales question via safe read-only tools (not freeform SQL)."""
    result = answer_question(db, payload.question)
    return AgentQueryResponse(**result)
