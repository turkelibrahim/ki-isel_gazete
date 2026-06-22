# E-Gazete Compact Size Fix

Bu paket, kullanıcının son ekran görüntüsünde görülen aşırı büyük e-Gazete sayfa ölçeğini düzeltir.

## Yapılanlar

- Ana e-Gazete konteyner genişliği 1368px yerine daha kompakt 1288px seviyesine çekildi.
- Gazete sayfalarının minimum yüksekliği viewport'a göre düşürüldü.
- Büyük masthead, manşet başlıkları, haber görselleri ve sağ kaynak paneli oranları küçültüldü.
- İki sayfa + sağ kaynak paneli düzeni korundu.
- Sağdaki aç/kapat kaynak paneli korundu.
- Mobil/tablet responsive davranış bozulmadı.
- Cache karışmaması için index asset versiyonu yenilendi.

## Korunanlar

- E-Gazete görünümü
- Sağ kaynak paneli
- Aç/kapat panel davranışı
- PDF butonu
- Haber detay / kaynak geçiş sistemi
- Backend endpointleri
- database.py ve main.py
