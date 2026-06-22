# E-Gazete Gerçek Gazete Deneyimi Entegrasyonu

Bu paket, kullanıcının istediği gerçek gazete yaprağı hissini frontend koduna entegre eder.

## Eklenen davranışlar

- E-Gazete modu artık modern kart görünümü yerine fiziksel gazete / dergi sayfası düzeniyle render edilir.
- Haber seçkisi üç ana kaynaktan harmanlanır:
  - kullanıcının kişisel öneri haberleri,
  - gündem / trend haberleri,
  - kullanıcının Kaynaklarım bölümünde eklediği RSS / site / YouTube içerikleri.
- Haberlerin kendi `imageUrl`, `image`, `urlToImage`, `thumbnailUrl` alanları kullanılır.
- Görsel yoksa sadece güvenli placeholder görseller devreye girer.
- E-Gazete içinde sayfa çevirme hissi için paper curl, stack, shadow ve geçiş animasyonu eklendi.
- Kategori sekmeleri gerçek gazete bölümleri gibi çalışır: Editör, Gündem, Dünya, Ekonomi, Spor, Bilim ve Teknoloji, Kültür & Sanat, Yaşam, Kaynaklarım, Trend.
- PDF butonu kişisel, kaynak ve trend haberleri birlikte basacak parametrelerle çalışır.
- Mevcut backend modüllerine, `database.py` dosyasına ve auth/report/admin sistemine dokunulmadı.

## Değişen dosyalar

- `js/components/eGazeteMode.js`
- `js/app.js`
- `css/egazete.css`
- `dist/app.min.js`
- `dist/style.min.css`
- `index.html`

## Not

Bu entegrasyon tamamen mevcut veri akışına bağlıdır. Yani canlı RSS/API/kaynak haberleri geldikçe E-Gazete sayfaları otomatik olarak o haberlerin başlık, özet, kaynak ve görselleriyle şekillenir.
