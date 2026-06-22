# Modül 1 — Data Collection Genel Akış

Bu bölüm, haber toplama katmanının sistem içinde uçtan uca nasıl çalışacağını özetler.

## Sistem nasıl çalışacak?

1. Sistem aktif haber kaynaklarını `sources` tablosundan okur.
2. Kaynak RSS ise `rss_service` çalışır.
3. Kaynak API ise `news_api_service` çalışır.
4. Kaynak HTML crawl istiyorsa `spider_manager` çalışır.
5. Gelen haber normalize edilir.
6. URL bazlı duplicate için PostgreSQL `ON CONFLICT DO NOTHING` uygulanır.
7. Dil tespiti yapılır.
8. Kaynak metadata bilgisi çıkarılır.
9. MinHash + LSH ile benzer haber kontrol edilir.
10. Haber `articles` tablosuna kaydedilir.
11. Duplicate ise `is_duplicate=True` olur.
12. Celery Beat bu işlemleri belirlenen aralıklarla otomatik tekrarlar.

## Kurulum Komutları — Modül 1 Toplu

```bash
pip install httpx beautifulsoup4 lxml
pip install feedparser langdetect python-dateutil
pip install celery[redis] redis
pip install arrow
pip install datasketch
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Kontrol Listesi

- [x] `POST /api/crawl/run` route import ve FastAPI wiring çalışıyor.
- [~] RSS kaynaklarından haber gelmesi canlı kaynak ve veritabanı bağlantısı gerektirir; `RSSService` aktif kaynakları okuyup normalize edecek şekilde hazır.
- [x] NewsAPI rate limit `NEWSAPI_RATE_LIMIT_SECONDS=36` ile istekten önce bekliyor.
- [x] Celery worker ve beat task import/schedule wiring hazır.
- [x] Dil tespiti `language` alanını `save_article()` içinde dolduruyor.
- [x] Citation endpoint kaynak bilgisini döndürecek şekilde eklendi: `GET /api/articles/{article_id}/citation`.
- [x] Aynı URL iki kez kaydedilmesin diye PostgreSQL `ON CONFLICT DO NOTHING` kullanılıyor.
- [x] Farklı URL ama aynı içerik MinHash + LSH + Jaccard ile duplicate yakalanıyor.
- [x] `main.py` sadece FastAPI app oluşturma ve router import/include wiring için kullanılıyor.
- [x] `database.py` değiştirilmedi.

## Sonraki Parça

Sıradaki geliştirme paketi: **Parça 2 — News Classification**.

---
