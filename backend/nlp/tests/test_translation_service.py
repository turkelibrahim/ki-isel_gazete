from backend.nlp.models import RawArticle
from backend.nlp.translation_service import prepare_translation_fields


def test_turkish_translation_fields_are_prepared():
    raw = RawArticle(id="1", title="Başlık", content="İçerik")
    result = prepare_translation_fields(raw, "tr")
    assert result.title_tr == "Başlık"
    assert result.content_tr == "İçerik"


def test_english_without_provider_is_skipped():
    raw = RawArticle(id="1", title="Title", content="Content")
    result = prepare_translation_fields(raw, "en")
    assert result.title_en == "Title"
    assert result.translation_status in {"skipped", "queued"}
