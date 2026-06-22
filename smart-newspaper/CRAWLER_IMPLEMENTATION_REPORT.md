# PROMPT 01 — Automated Web Crawling Implementation Report

## Eklenen yapı

Python/FastAPI crawler backend katmanı eklendi:

- `backend/app/crawlers/base_spider.py`
- `backend/app/crawlers/news_spider.py`
- `backend/app/crawlers/spider_manager.py`
- `backend/app/routers/crawl.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/database.py`
- `backend/requirements.txt`
- `backend/README_CRAWLER.md`

## Karşılanan gereksinimler

- Template Method Pattern: `BaseSpider` ortak crawl akışını yönetir; kaynak bazlı spider yalnızca `parse()` override eder.
- Rastgele rate limit: her HTTP isteğinden önce `asyncio.sleep(random.uniform(1.5, 3.5))` çalışır.
- User-Agent rotasyonu: 5 gerçek tarayıcı UA tanımlandı ve her istekte `random.choice()` kullanılır.
- `robots.txt`: `urllib.robotparser.RobotFileParser` ile kontrol edilir; okunamazsa fail-open + warning log.
- Async HTTP: `httpx.AsyncClient(timeout=15, follow_redirects=True)` kullanıldı.
- HTML parse: BeautifulSoup ile `article`, `.article`, `.news-item` ve benzeri kartlardan haber çıkarılır.
- PostgreSQL upsert: `insert(Article).values(...).on_conflict_do_nothing(index_elements=["url"])` kullanıldı.
- Spider manager: aktif kaynakları DB’den alır, tüm kaynakları sırayla izole try/except ile çalıştırır.
- API: `POST /api/crawl/run` ve `GET /api/crawl/status` eklendi.
- Fonksiyonlarda type hint ve docstring kullanıldı.

## Doğrulama

- `python -m py_compile backend/**/*.py` başarılı.
- FastAPI route import kontrolü başarılı: `/api/crawl/run`, `/api/crawl/status`, `/api/health` görünüyor.
- Örnek HTML ile `NewsSpider.parse()` smoke test başarılı.
- Mevcut Node testleri: `npm test` → 70/70 passed.
- `npm run build` denenmiştir; ortamda Windows için kurulmuş esbuild (`@esbuild/win32-x64`) bulunduğu için Linux sandbox’ta başarısız oldu. Bu yeni crawler kodundan bağımsız mevcut `node_modules` platform uyumsuzluğudur. Kendi Windows makinenizde veya `npm ci` sonrası doğru platformda çalışmalıdır.
