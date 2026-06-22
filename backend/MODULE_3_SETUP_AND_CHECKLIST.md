# MODÜL 3 — Personal Newspaper Toplu Kurulum ve Kontrol Listesi

Bu dosya Modül 3 kapsamındaki P12, P13, P14, P15, P16 ve P17 çalışmalarının kurulum komutlarını, genel akışını ve doğrulama kontrol listesini içerir.

## Modül 3 Toplu Kurulum

```bash
pip install scikit-learn scipy numpy redis
pip install jinja2 arrow
pip install celery[redis] redis
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 3 Genel Akış

1. Kullanıcının okuduğu haberler `user_events` tablosundan alınır.
2. Kullanıcının okuduğu haberlerden TF-IDF ortalama vektörü çıkarılır.
3. Content-Based öneri skoru hesaplanır.
4. Benzer kullanıcıların okuduğu haberlerden Collaborative Filtering skoru hesaplanır.
5. CB `%60` + CF `%40` hibrit skor üretilir.
6. Cold start kullanıcı için `user_interests` + popüler haber fallback uygulanır.
7. Kullanıcı filtreleriyle haber listesi daraltılır.
8. Manşet sıralaması temporal decay + relevance + popularity + trust skoruyla yapılır.
9. Jinja2 template ile dijital gazete HTML’i üretilir.
10. Citation bilgileri her haberin altına eklenir.
11. `newspaper_editions` tablosuna `html_content` kaydedilir.
12. Sonraki Modül 4’te aynı HTML PDF’e dönüştürülecek.

## P12 / P13 / P14 / P15 / P16 / P17 Endpoint Özeti

### P12 — Hybrid Recommender

```bash
GET  /api/personal/feed?user_id=<USER_ID>&limit=30
GET  /api/personal/feed/{user_id}?limit=30
POST /api/personal/rebuild-index?language=tr
GET  /api/personal/recommendation-debug?user_id=<USER_ID>
```

### P13 — Article Filtering

```bash
GET /api/articles?category_id=1&source_ids=1,2&date_from=2026-06-01&language=tr&sort_by=popularity&page=1&page_size=20
```

### P14 — Newspaper Layout Preview

```bash
POST /api/newspaper/preview-html
```

### P15 — Headline Prioritization

```bash
POST /api/newspaper/rank-headlines
GET  /api/articles/top-headlines
```

### P16 — Newspaper Citations

```bash
GET  /api/newspaper/articles/{article_id}/citation
POST /api/newspaper/citations/batch
```

### P17 — Newspaper Edition Pipeline

```bash
POST   /api/newspaper/editions/generate
GET    /api/newspaper/editions/me?user_id=<USER_ID>
GET    /api/newspaper/editions/{edition_id}
DELETE /api/newspaper/editions/{edition_id}
```

## Modül 3 Kontrol Listesi

- [x] Hybrid recommender CB `%60` + CF `%40` çalışıyor.
- [x] Okunmuş haberler öneriden çıkarılıyor.
- [x] Cold start `user_interests` + popüler haber fallback çalışacak şekilde servis akışı hazır.
- [x] Article filtering category/source/date/language destekliyor.
- [x] Pagination `page` / `page_size` ile doğru offset/limit üretiyor.
- [x] Duplicate haberler filtreleniyor.
- [x] Jinja2 `daily.html` gazete layout üretiyor.
- [x] Manşet `articles[0]` olarak en yüksek priority skorlu haber seçiliyor.
- [x] Temporal decay eski haberleri aşağı çekiyor.
- [x] Citation bilgisi her haber altında görünüyor.
- [x] Edition pipeline `html_content` üretiyor.
- [x] `newspaper_editions` tablosuna kayıt atılıyor.
- [x] Celery daily edition task tanımlandı.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece router include için değişti.

## Notlar

- `database.py` dosyasına dokunulmadı.
- Frontend UI/CSS/HTML dosyalarına dokunulmadı; ekran kayması oluşturacak değişiklik yapılmadı.
- P17 ile üretilen `html_content`, Modül 4 PDF export için hazır tutulur.
