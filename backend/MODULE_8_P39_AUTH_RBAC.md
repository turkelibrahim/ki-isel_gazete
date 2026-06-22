# Modül 8 / P39 — JWT Authentication + RBAC Authorization

Bu parça Smart Personnel Newspaper backend içinde JWT tabanlı authentication ve role-based access control katmanını ekler.

## Kurulum

```bash
pip install python-jose passlib[bcrypt] python-multipart email-validator
```

## ENV

```env
SECRET_KEY=32_karakterden_uzun_rastgele_secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

`SECRET_KEY` dosyaya hardcode edilmez. Development ortamında eksikse warning loglanır; production ortamında zorunludur.

## Endpointler

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

## Token Kuralları

Access token payload:

```json
{
  "sub": "<user_id>",
  "role": "USER|EDITOR|ADMIN",
  "type": "access",
  "exp": "..."
}
```

Refresh token payload:

```json
{
  "sub": "<user_id>",
  "role": "USER|EDITOR|ADMIN",
  "type": "refresh",
  "exp": "..."
}
```

- Access token ömrü: `30 dakika`
- Refresh token ömrü: `7 gün`
- Protected endpointlerde refresh token kabul edilmez.
- Refresh endpointinde access token kabul edilmez.
- Password veya `password_hash` hiçbir response içinde dönmez.

## RBAC Matrix

| Role | İzinler |
|---|---|
| ADMIN | read, write, delete, admin, manage_sources, view_reports, moderate |
| EDITOR | read, write, manage_sources, moderate |
| USER | read, write_own |

Dependency kullanımı:

```python
Depends(require_role("ADMIN"))
Depends(require_role("ADMIN", "EDITOR"))
```

## P36/P37/P38 Entegrasyonu

Aşağıdaki admin korumaları artık gerçek JWT/RBAC dependency kullanır:

- `/api/admin/*` → `Depends(require_role("ADMIN"))`
- `/api/monitoring/metrics` → `Depends(require_role("ADMIN"))`
- `/api/monitoring/logs/recent` → `Depends(require_role("ADMIN"))`
- `/api/reports/*` → `Depends(require_role("ADMIN"))`

`/api/monitoring/health` public kalır.

## Eklenen Dosyalar

- `backend/app/core/security.py`
- `backend/app/dependencies/__init__.py`
- `backend/app/dependencies/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/schemas/auth.py`
- `backend/app/routers/auth.py`
- `backend/migrations/20260621_add_user_password_hash.sql`

## Güncellenen Dosyalar

- `backend/app/models.py` → `User.password_hash`
- `backend/app/routers/admin.py` → gerçek `require_role("ADMIN")`
- `backend/app/routers/monitoring.py` → gerçek `require_role("ADMIN")`
- `backend/app/routers/reports.py` → gerçek `require_role("ADMIN")`
- `backend/app/main.py` → auth router include
- `backend/requirements.txt`
- `.env.example`

## Doğrulama

- Register password hash üretir.
- Login access token ve refresh token döndürür.
- `/api/auth/me` sadece access token ile çalışır.
- Refresh token protected endpointlerde reddedilir.
- Access token refresh endpointinde reddedilir.
- ADMIN endpointleri USER rolü için 403 döner.
- `database.py` değişmez.
- `main.py` sadece router include için değişir.
