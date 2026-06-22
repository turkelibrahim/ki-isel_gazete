from backend.nlp.models import RawArticle
from backend.nlp.newspaper_formatter import format_for_newspaper


def test_newspaper_formatter_outputs_fields():
    raw = RawArticle(id="1", title="Çok Uzun Haber Başlığı", content="Uzun içerik", summary="Kısa özet", category="Ekonomi")
    result = format_for_newspaper(raw, ["ekonomi", "piyasa"])
    assert result["newspaper_title"]
    assert result["newspaper_summary"]
    assert result["page_category"] == "Ekonomi"
