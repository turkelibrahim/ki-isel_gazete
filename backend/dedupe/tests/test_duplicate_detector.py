from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

from backend.dedupe.duplicate_detector import DedupeConfig, DuplicateDetector
from backend.dedupe.hasher import canonicalize_url, exact_article_hash
from backend.dedupe.text_cleaner import normalize_title


BASE_TIME = datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc)


def article(idx: int, title: str, content: str, source: str = "Kaynak", *, minutes: int = 0, url: str | None = None, trust: float = 60):
    return {
        "id": f"a{idx}",
        "title": title,
        "summary": content[:180],
        "fullText": content,
        "sourceName": source,
        "sourceLogo": f"/assets/sources/{source.lower()}.svg",
        "sourceUrl": url or f"https://example.com/{idx}?utm_source=x&fbclid=abc",
        "publishedAt": (BASE_TIME + timedelta(minutes=minutes)).isoformat(),
        "category": "Gündem",
        "trustScore": trust,
    }


def detector() -> DuplicateDetector:
    return DuplicateDetector(DedupeConfig(duplicate_threshold=0.85, discard_threshold=0.95))


def test_canonicalize_url_removes_tracking_but_keeps_real_params():
    url = canonicalize_url("https://www.hurriyet.com.tr/haber?id=42&utm_source=x&fbclid=y#giris")
    assert url == "https://hurriyet.com.tr/haber?id=42"


def test_hash_and_normalization_preserve_turkish_characters():
    normalized = normalize_title("Son Dakika: Merkez Bankası açıklama yaptı")
    assert "ı" in normalized
    assert exact_article_hash("Başlık", "İçerik") == exact_article_hash(" başlık!!!", "içerik")


def test_birebir_ayni_iki_haber_discarded_cluster():
    items = [
        article(1, "Merkez Bankası faiz kararını açıkladı", "Merkez Bankası bugün yeni faiz kararını açıkladı.", "AA"),
        article(2, "Merkez Bankası faiz kararını açıkladı", "Merkez Bankası bugün yeni faiz kararını açıkladı.", "TRT"),
    ]
    clusters = detector().detect_and_cluster(items)
    assert len(clusters) == 1
    payload = clusters[0].to_payload()
    assert payload["source_count"] == 2
    assert payload["duplicate_score"] == 1.0
    assert payload["dedupe_status"] == "discarded"


def test_yuzde_90_benzer_iki_haber_merge():
    items = [
        article(1, "Bakanlık yeni destek paketini açıkladı", "Bakanlık küçük işletmeler için yeni destek paketini açıkladı. Paket başvuruları temmuz ayında başlayacak.", "AA"),
        article(2, "Bakanlık destek paketini duyurdu", "Bakanlık küçük işletmeler için yeni destek paketini duyurdu. Başvuruların temmuz ayında başlayacağı bildirildi.", "Hürriyet"),
    ]
    clusters = detector().detect_and_cluster(items)
    assert len(clusters) == 1
    assert clusters[0].duplicate_score >= 0.85
    assert clusters[0].dedupe_status == "merged"


def test_yuzde_70_benzer_ama_farkli_haber_keep():
    items = [
        article(1, "Ekonomi yönetimi destek paketini açıkladı", "Küçük işletmeler için yeni kredi destek paketi ve başvuru takvimi açıklandı.", "AA"),
        article(2, "Ekonomi piyasalarında haftalık kapanış", "Borsa haftayı yükselişle kapatırken döviz ve altın fiyatlarında sınırlı hareket izlendi.", "NTV"),
    ]
    clusters = detector().detect_and_cluster(items)
    assert len(clusters) == 2
    assert all(cluster.dedupe_status == "unique" for cluster in clusters)


def test_baslik_ayni_icerik_farkli_haber_silinmez():
    items = [
        article(1, "Son dakika gelişmesi", "Ankara'da ulaşımla ilgili yeni metro hattı çalışmaları bugün başladı ve belediye takvimi duyurdu.", "AA"),
        article(2, "Son dakika gelişmesi", "İstanbul'da etkili olan sağanak yağış nedeniyle bazı vapur seferleri geçici olarak iptal edildi.", "TRT"),
    ]
    clusters = detector().detect_and_cluster(items)
    assert len(clusters) == 2


def test_icerik_ayni_baslik_farkli_haber_clusterlanir():
    content = "Yeni uydu sistemi için fırlatma hazırlıkları tamamlandı ve ekipler son teknik kontrolleri bitirdi."
    items = [
        article(1, "Uydu sistemi fırlatmaya hazırlanıyor", content, "AA"),
        article(2, "Uzay programında yeni aşama", content, "BBC Türkçe"),
    ]
    clusters = detector().detect_and_cluster(items)
    assert len(clusters) == 1
    assert clusters[0].to_payload()["source_count"] == 2


def test_uc_farkli_kaynakta_ayni_haber_sources_dogru_olusur():
    items = [
        article(1, "Yeni hızlı tren hattı açıldı", "Yeni hızlı tren hattı açıldı ve ilk sefer sabah saatlerinde yapıldı.", "AA", minutes=0, trust=80),
        article(2, "Hızlı tren hattında ilk sefer yapıldı", "Yeni hızlı tren hattı açıldı ve ilk sefer sabah saatlerinde gerçekleştirildi.", "TRT", minutes=10, trust=90),
        article(3, "Yeni hızlı tren hattı hizmete girdi", "Yeni hızlı tren hattı açıldı ve ilk sefer sabah saatlerinde yapıldı.", "NTV", minutes=20, trust=70),
    ]
    payload = detector().to_payload(items)[0]
    assert payload["source_count"] == 3
    assert {source["source_name"] for source in payload["sources"]} == {"AA", "TRT", "NTV"}
    assert payload["main_article"]["sourceName"] == "TRT"


def test_bos_icerikli_haber_sistemi_cokertmez():
    clusters = detector().detect_and_cluster([article(1, "Boş içerik", "", "AA"), article(2, "Başka boş", "", "TRT")])
    assert len(clusters) == 2


def test_tek_haberlik_batch_unique_payload():
    payload = detector().to_payload([article(1, "Tek haber", "Sadece tek haber var.", "AA")])[0]
    assert payload["source_count"] == 1
    assert payload["dedupe_status"] == "unique"
    assert payload["cluster_id"]


def test_100_haber_performans_testi():
    items = []
    for i in range(100):
        group = i // 10
        items.append(article(i, f"Şehirde altyapı çalışması {group}", f"Şehirde altyapı çalışması {group} için ekipler bugün sahaya indi ve yeni plan açıklandı.", f"Kaynak{i % 7}"))
    start = time.perf_counter()
    clusters = detector().detect_and_cluster(items)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0
    assert len(clusters) <= 15


def test_sources_listesi_haber_karti_icin_uyumlu():
    payload = detector().to_payload([
        article(1, "Enerji yatırımı açıklandı", "Enerji yatırımı için yeni finansman ve uygulama takvimi açıklandı.", "AA"),
        article(2, "Enerji yatırımı duyuruldu", "Enerji yatırımı için yeni finansman ve uygulama takvimi duyuruldu.", "Hürriyet"),
    ])[0]
    source = payload["sources"][0]
    required = {"source_name", "source_logo", "source_url", "title", "published_at", "articleId", "sourceName", "sourceIcon", "sourceUrl"}
    assert required.issubset(source.keys())
