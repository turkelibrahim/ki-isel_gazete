# Şehrindeki Etkinlikler — Multi-Source Event Adapter Sistemi

Bu paket içinde SmartNewspaper etkinlik ekranı Biletix odaklı tek kaynak hissinden çıkarılıp multi-source profesyonel etkinlik keşif modülüne dönüştürüldü.

## Backend

Yeni adapter mimarisi:

- `server/events/eventSources.js`
- `server/events/normalizeEvent.js`
- `server/events/eventAggregator.js`
- `server/events/sources/biletixAdapter.js`
- `server/events/sources/biletinialAdapter.js`
- `server/events/sources/bubiletAdapter.js`
- `server/events/sources/passoAdapter.js`
- `server/events/sources/mobiletAdapter.js`
- `server/events/sources/ticketmasterAdapter.js`
- `server/events/sources/eventbriteAdapter.js`
- `server/events/sources/meetupAdapter.js`
- `server/events/sources/cultureIstanbulAdapter.js`
- `server/events/sources/ibbCultureAdapter.js`
- `server/events/sources/zorluPsmAdapter.js`
- `server/events/sources/akmAdapter.js`
- `server/events/sources/etkinlikIoAdapter.js`
- `server/events/sources/festivallAdapter.js`
- `server/events/sources/minikaAdapter.js`

Desteklenen kaynak katalogları:

- Biletix
- Biletinial
- Bubilet
- Passo
- Mobilet
- Ticketmaster
- Eventbrite
- Meetup
- Kültür İstanbul
- İBB Kültür Sanat
- Zorlu PSM
- AKM İstanbul
- Etkinlik.io
- Festivall
- Minika Çocuk

## Standart event modeli

Aggregator tüm kaynakları şu modele çevirir:

```js
{
  id,
  title,
  description,
  category,
  startDate,
  endDate,
  city,
  district,
  venueName,
  venueAddress,
  latitude,
  longitude,
  priceMin,
  priceMax,
  currency,
  ticketUrl,
  sourceName,
  sourceLogo,
  sourceEventId,
  imageUrl,
  imageAlt,
  imageCredit,
  isFree,
  tags,
  popularityScore,
  createdAt,
  updatedAt
}
```

## Dedupe / kaynak birleştirme

Aynı etkinlik farklı kaynaklardan gelirse tek karta toplanır.

Sinyaller:

- normalize edilmiş başlık
- tarih yakınlığı
- mekan adı
- şehir
- kategori

Cluster içinde `sources` listesi tutulur. Kart altında kaynak ikonları gösterilir.

## Endpointler

- `GET /api/events?city=ISTANBUL&category=Tümü&date=Bu%20Hafta&q=&source=Tüm%20Kaynaklar&limit=24&page=1`
- `POST /api/events/refresh`
- `GET /api/events/:id`
- `GET /api/events/:id/ics`
- `GET /api/events/image-proxy?url=...`

## Frontend

Etkinlik ekranı şu başlıkla güncellendi:

- Başlık: `Şehrindeki Etkinlikler`
- Açıklama: `Konser, tiyatro, festival ve daha fazlasını güvenilir kaynaklardan keşfet.`

Kartlar:

- 16:9 etkinlik görseli
- kategori rozeti
- favori butonu
- kaynak logosu
- tarih rozeti
- mekan / şehir
- fiyat veya ücretsiz bilgisi
- kaynak ikonları
- Detayları Gör
- Bilet Al
- Takvime Ekle
- Hatırlatıcı Kur

## Görsel fallback

Her etkinlikte görsel bulunmaya çalışılır. Kaynak görseli yoksa kategoriye göre kaliteli fallback URL atanır:

- Konser
- Tiyatro
- Festival
- Stand-up
- Spor
- Sergi
- Çocuk
- Etkinlik

## Testler

Eklenen test dosyası:

- `js/tests/event-aggregator.test.mjs`

Kapsam:

- normalizeEvent modeli
- fallback görsel
- dedupe cluster
- benzerlik eşiği

## Korunan sistemler

- Haber akışı
- E-Gazete
- PDF
- Takvim
- Feedback merkezi
- Kaynaklarım
- TR/EN sistemi
- Taze Haberleri Getir
