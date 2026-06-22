from datetime import datetime
from backend.nlp.language_processor import detect_language, choose_pipeline, process_article
from backend.nlp.models import RawArticle


def test_turkish_pipeline_selected():
    result = detect_language("Türkiye ekonomisi bugün önemli bir karar açıkladı ve piyasalar bunu yakından izliyor.")
    assert result.detected_lang == "tr"
    assert choose_pipeline(result) == "turkish"


def test_english_pipeline_selected():
    result = detect_language("The economy has been growing this year and the government announced new market rules.")
    assert result.detected_lang == "en"
    assert choose_pipeline(result) == "english"


def test_empty_is_unknown():
    result = detect_language("   ")
    assert result.detected_lang == "unknown"
    assert not result.is_reliable


def test_process_article_outputs_newspaper_fields():
    article = RawArticle(
        id="1",
        title="Merkez Bankası faiz kararını açıkladı",
        content="Türkiye Cumhuriyet Merkez Bankası yeni faiz kararını açıkladı.",
        summary="Merkez Bankası kararı açıklandı.",
        source_name="Demo",
        source_url="https://example.com/?utm_source=x",
        fetched_at=datetime.utcnow(),
    )
    processed = process_article(article)
    assert processed.processing_status in {"success", "partial"}
    assert processed.dedupe_key
    assert processed.cluster_id
