"""Validation tests for LLM categorizer outputs."""
from __future__ import annotations

from backend.llm_categorizer.utils.validator import parse_and_validate_response, validate_categories


def test_valid_json_is_accepted() -> None:
    result = parse_and_validate_response('{"categories":["Teknoloji"],"confidences":{"Teknoloji":0.95},"reasoning":"AI çipi"}')
    assert result is not None
    assert result.categories == ["Teknoloji"]


def test_markdown_json_is_parsed() -> None:
    result = parse_and_validate_response('```json\n{"categories":["Ekonomi"],"confidences":{"Ekonomi":0.91},"reasoning":"Faiz"}\n```')
    assert result is not None
    assert result.categories == ["Ekonomi"]


def test_invalid_category_is_rejected() -> None:
    assert parse_and_validate_response('{"categories":["Gündem"],"confidences":{"Gündem":0.99},"reasoning":"x"}') is None


def test_duplicate_categories_are_unique() -> None:
    result = parse_and_validate_response('{"categories":["Spor","Spor"],"confidences":{"Spor":0.88},"reasoning":"Maç"}')
    assert result is not None
    assert result.categories == ["Spor"]


def test_plain_text_is_rejected() -> None:
    assert parse_and_validate_response("Bu haber teknoloji ile ilgili") is None


def test_validate_categories() -> None:
    assert validate_categories(["Teknoloji", "Ekonomi"]) is True
    assert validate_categories(["Teknoloji", "Diğer"]) is False
