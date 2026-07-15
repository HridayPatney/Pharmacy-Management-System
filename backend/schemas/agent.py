"""Inventory chat / NL agent schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Natural-language inventory question."""

    question: str = Field(min_length=1, max_length=500)


class AgentQueryResponse(BaseModel):
    """Answer plus the read-only plan that was used (SQL and/or tool)."""

    answer: str
    tool: str | None = None
    mode: str = "tool"
    sql: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0
    rows: list[dict[str, Any]] = Field(default_factory=list)
