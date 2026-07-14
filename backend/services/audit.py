"""Persist audit events for sensitive inventory actions."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.db import models


def write_audit(
    db: Session,
    *,
    user: models.User,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, Any] | str | None = None,
) -> models.AuditLog:
    """Append an audit log row (caller commits or includes in the same transaction)."""
    if isinstance(details, dict):
        detail_text = json.dumps(details, default=str)
    else:
        detail_text = details

    entry = models.AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=detail_text,
    )
    db.add(entry)
    return entry
