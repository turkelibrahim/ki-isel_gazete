# Modül 6 / P29 — Bookmark CRUD / Optimistic Upsert

Bu dosya kullanıcıların haberleri yer imlerine ekleyip kaldırabilmesi için eklenen bookmark sistemini özetler.

## Eklenen Dosyalar

- `backend/app/services/bookmark_service.py`
- `backend/app/schemas/bookmarks.py`
- `backend/app/routers/bookmarks.py`
- `backend/migrations/20260621_add_user_bookmarks.sql`

## Endpointler

```bash
GET    /api/bookmarks?user_id=<USER_ID>&page=1&page_size=20
POST   /api/bookmarks/{article_id}?user_id=<USER_ID>
DELETE /api/bookmarks/{article_id}?user_id=<USER_ID>
POST   /api/bookmarks/{article_id}/toggle?user_id=<USER_ID>
GET    /api/bookmarks/{article_id}/status?user_id=<USER_ID>
```

> TODO(auth): FastAPI auth dependency bağlanınca geçici `user_id` query/body parametresi `current_user.id` ile değiştirilecek. Normal kullanıcı sadece kendi bookmark kayıtlarını görecek; ADMIN başka kullanıcıların kayıtlarını yönetebilecek.

## Optimistic Upsert Mantığı

`add_bookmark()` içinde duplicate kontrolü için önce `SELECT` yapılmaz.

1. `Article` varlığı kontrol edilir.
2. `is_duplicate=True` ise `400` döner.
3. `UserBookmark(user_id, article_id)` doğrudan eklenir.
4. `db.commit()` denenir.
5. `IntegrityError` gelirse rollback yapılır ve şu response döner:

```json
{
  "status": "already_exists",
  "bookmarked": true
}
```

Bu davranış `UNIQUE(user_id, article_id)` constraint’ini source of truth yapar ve SELECT + INSERT yarış riskini azaltır.

## User Events Entegrasyonu

- Bookmark eklenince `user_events.event_type = "BOOKMARKED"` kaydı yazılır.
- Bookmark kaldırılınca opsiyonel öğrenme sinyali olarak `event_type = "UNBOOKMARKED"` kaydı yazılır.
- Böylece P12 hibrit öneri sistemi bookmark davranışından öğrenebilir.

## Kontrol Listesi

- [x] `BookmarkService` oluşturuldu.
- [x] `BookmarkCreate`, `BookmarkResponse`, `BookmarkListResponse`, `BookmarkStatusResponse` şemaları oluşturuldu.
- [x] `bookmarks` router oluşturuldu.
- [x] `UserBookmark` modeli eklendi.
- [x] `UNIQUE(user_id, article_id)` migration script’i eklendi.
- [x] Aynı article iki kez bookmark edilince duplicate kayıt oluşmaz.
- [x] `IntegrityError` yakalanıp sistem çökmeden `already_exists` döner.
- [x] Bookmark listesi `created_at DESC` döner.
- [x] Status endpoint true/false döner.
- [x] Toggle endpoint ekleme/kaldırma yapar.
- [x] `user_events` içine `BOOKMARKED` yazılır.
- [x] Duplicate haber bookmark edilmez.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece bookmark router import/include için değişti.
