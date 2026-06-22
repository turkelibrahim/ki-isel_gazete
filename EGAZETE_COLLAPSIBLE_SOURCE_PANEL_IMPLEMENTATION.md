# E-Gazete Açılır/Kapanır Kaynak Paneli ve 2 Sayfa Düzeni

Bu paket, kullanıcının istediği e-Gazete sağ kaynak sütunu davranışını kod olarak ekler.

## Eklenenler

- Sağdaki **Seçtiğiniz Kaynaklar / Köşe Analiz** sütunu artık açılır-kapanır paneldir.
- Panel açıkken sağ sütun aynı yerde korunur.
- Kullanıcı **Gizle** dikey tutamacına basınca panel kapanır.
- Panel kapalıyken küçük **Kaynaklar** sekmesi görünür; kullanıcı buna basınca panel geri gelir.
- Panel durumu `localStorage` içinde saklanır.
- Ana e-Gazete alanı artık temiz iki sayfa olarak düzenlenir.
- Her gazete sayfasında iki haber gösterilir.
- Sağ kaynak sütunu ana gazete sayfalarını bozmaz.
- Mobilde panel taşmadan alt kısımda açılır/kapanır.

## Korunanlar

- E-Gazete modu
- PDF indir
- Kategori sekmeleri
- Kişisel/trend/kaynak haber mantığı
- Haber görselleri
- Haber detay açma
- No-cache düzeni
- Backend modülleri
- database.py
- main.py

## Değişen Ana Dosyalar

- `js/components/eGazeteMode.js`
- `css/egazete.css`
- `dist/app.min.js`
- `dist/style.min.css`
- `index.html`

## Test

- `node -c js/components/eGazeteMode.js`
- `node -c js/app.js`
- `node -c dist/app.min.js`
- `python -m compileall -q backend`
- `npm test`
- `npm run build`
