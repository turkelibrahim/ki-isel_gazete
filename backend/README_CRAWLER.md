# Modül 1 — Sistem Nasıl Çalışır?

Genel akış, kurulum komutları ve kontrol listesi için `backend/MODULE_1_DATA_COLLECTION.md` dosyasına bak.

---

# Automated Web Crawling Backend

Bu klasör `PROMPT 01 — Automated Web Crawling` gereksinimlerine göre eklendi.

## Kurulum

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

PostgreSQL bağlantısı için:

```bash
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/smart_newspaper
```

Çalıştırma:

```bash
uvicorn app.main:app --reload
```

## Endpointler

- `POST /api/crawl/run` → `{ "crawled": N, "errors": M }`
- `GET /api/crawl/status` → son crawl zamanı, son hata sayısı, aktif kaynak sayısı

## Notlar

- Crawler her istekten önce `asyncio.sleep(random.uniform(1.5, 3.5))` kullanır.
- Her istekte User-Agent rastgele seçilir.
- `robots.txt` okunamazsa sistem fail-open çalışır ve warning log basar.
- Duplicate URL için PostgreSQL `ON CONFLICT DO NOTHING` kullanılır.
