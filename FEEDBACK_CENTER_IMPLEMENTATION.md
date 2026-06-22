# SmartNewspaper — Sağ Alt İkonlu Geri Bildirim Merkezi

Bu paket, SmartNewspaper / Kişisel Gazetem arayüzüne sağ alt köşede sadece ikonlu, kompakt bir geri bildirim merkezi ekler.

## Kullanıcı tarafı

- Sağ alt köşede 52x52 px ikonlu floating action button bulunur.
- Buton içinde yazı yoktur; sadece mesaj ikonu görünür.
- Hover tooltip: `Geri Bildirim Gönder`.
- Tıklanınca modern modal açılır.
- Modal sekmeleri:
  - Geri Bildirim Gönder
  - Mesajlarım
- Form alanları:
  - Konu
  - Geri Bildirim Türü
  - 1-5 yıldız memnuniyet
  - Öncelik
  - Mesaj + 1000 karakter sayacı
- Kullanıcı giriş yapmamışsa mesaj gönderemez ve uyarı görür.
- Kullanıcı sadece kendi mesaj geçmişini görebilir.

## Backend tarafı

Yeni kullanıcı endpointleri:

```http
POST /api/feedback
GET  /api/feedback/my
GET  /api/feedback/my/:id
```

Yeni admin endpointleri:

```http
GET   /api/admin/feedback
GET   /api/admin/feedback/:id
PATCH /api/admin/feedback/:id/status
POST  /api/admin/feedback/:id/reply
PATCH /api/admin/feedback/:id/archive
```

## Admin paneli

`admin.html` içine `Kullanıcı Geri Bildirimleri` sayfası eklendi.

Admin burada şunları görebilir:

- Kullanıcı adı ve e-posta
- Konu
- Mesaj
- Tür
- Öncelik
- Memnuniyet puanı
- Durum
- Gönderilme tarihi
- Sayfa / URL / cihaz / tarayıcı teknik bilgileri

Admin işlemleri:

- Durum güncelleme
- Kullanıcıya cevap yazma
- Çözüldü yapma
- Arşivleme

Admin cevap verdiğinde kullanıcının bildirimlerine şu mesaj eklenir:

```txt
Admin geri bildiriminize cevap verdi.
```

## Güvenlik

- HTML etiketleri düz metne çevrilir.
- XSS riskini azaltmak için frontend ve backend escape/sanitize uygular.
- Giriş yapmayan kullanıcı `POST /api/feedback` kullanamaz.
- Kullanıcı sadece kendi geri bildirimlerini görebilir.
- Admin endpointleri mevcut admin guard ile korunur.
- Basit rate limit: kullanıcı başına 10 dakikada 5 mesaj.

## Eklenen dosyalar

Frontend:

- `js/components/feedbackFloatingButton.js`
- `css/feedback.css`

Backend / Node:

- `services/feedbackService.js`
- `db/feedbackRepository.js`
- `routes/feedback.js`
- `routes/adminFeedback.js`
- `middleware/adminOnly.js`

Güncellenenler:

- `server.js`
- `js/app.js`
- `build.js`
- `admin.html`
- `index.html`
- `dist/app.min.js`
- `dist/style.min.css`

## Not

E-Gazete, haber kartları, PDF, paylaşım, kaynak paneli, kategori filtreleri, takvim, bildirimler ve no-cache düzeni korunmuştur.
