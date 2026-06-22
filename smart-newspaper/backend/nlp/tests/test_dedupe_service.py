from datetime import datetime
from backend.nlp.dedupe_service import canonicalize_url, normalize_title, title_similarity, build_dedupe_key
from backend.nlp.models import RawArticle


def test_canonicalize_url_removes_tracking():
    url = canonicalize_url("http://example.com/news/?utm_source=x&fbclid=y&id=1#frag")
    assert "utm_source" not in url
    assert "fbclid" not in url
    assert "#" not in url


def test_normalize_title_preserves_turkish_chars():
    assert "faiz" in normalize_title("Son Dakika: Merkez Bankası faiz kararını açıkladı!")
    assert "ı" in normalize_title("Açıklama yapıldı")


def test_title_similarity_same_event():
    assert title_similarity("Merkez Bankası faiz kararını açıkladı", "Merkez Bankası faiz kararı açıklandı") > 0.4


def test_build_dedupe_key_stable():
    raw = RawArticle(id="a", title="Başlık", content="İçerik", fetched_at=datetime(2026, 6, 21))
    assert build_dedupe_key(raw, "tr") == build_dedupe_key(raw, "tr")
