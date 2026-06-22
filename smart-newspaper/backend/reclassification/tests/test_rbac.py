from __future__ import annotations

import pytest

from backend.reclassification.utils.rbac import PermissionDenied, ensure_permission


def test_reviewer_cannot_trigger_retrain() -> None:
    with pytest.raises(PermissionDenied):
        ensure_permission("reviewer", "can_trigger_retrain")


def test_super_admin_can_trigger_retrain() -> None:
    ensure_permission("super_admin", "can_trigger_retrain")
