"""Validation helpers shared by API and task layers."""
from __future__ import annotations

from backend.reclassification.models.enums import ALLOWED_CATEGORY_VALUES


def validate_allowed_labels(labels: list[str]) -> list[str]:
    """Validate and return labels while enforcing the single source of truth."""
    if not labels:
        raise ValueError("En az bir kategori seçilmelidir.")
    invalid = [label for label in labels if label not in ALLOWED_CATEGORY_VALUES]
    if invalid:
        raise ValueError(f"Geçersiz kategori. İzin verilenler: {list(ALLOWED_CATEGORY_VALUES)}")
    if len(labels) != len(set(labels)):
        raise ValueError("Aynı kategori iki kez seçilemez.")
    return labels
