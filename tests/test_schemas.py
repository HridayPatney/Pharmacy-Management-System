"""Unit tests for inventory and sell request schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.inventory import SellItem, SellRequest


def test_sell_item_rejects_non_positive_quantity():
    with pytest.raises(ValidationError):
        SellItem(name="Aspirin", quantity=0)


def test_sell_request_accepts_valid_lines():
    req = SellRequest(medicines=[SellItem(name="Aspirin", quantity=2)])
    assert req.medicines[0].name == "Aspirin"
    assert len(req.medicines) == 1
