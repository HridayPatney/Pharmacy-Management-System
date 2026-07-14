"""Role names and permission helpers."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """Staff roles for PharmaAssist."""

    ADMIN = "admin"
    PHARMACIST = "pharmacist"
    CASHIER = "cashier"


# Routes that mutate catalog (not sales).
INVENTORY_WRITE_ROLES = (Role.ADMIN, Role.PHARMACIST)

# Anyone who can operate the counter.
STAFF_ROLES = (Role.ADMIN, Role.PHARMACIST, Role.CASHIER)
