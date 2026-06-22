# E-Gazete Referans Görünüm Düzenlemesi

Bu paket, kullanıcının gönderdiği referans ekran görüntüsüne göre e-Gazete okuma alanını kod seviyesinde günceller.

## Yapılanlar

- Ana gazete alanı iki sayfalı fiziksel gazete görünümünde sabitlendi.
- Sol sayfada büyük masthead + manşet + ikinci haber düzeni korundu.
- Orta/sağ gazete sayfası iki büyük haberli, temiz ve dengeli görünecek şekilde ayarlandı.
- En sağdaki kaynak/köşe paneli korunarak daha kompakt ve hizalı hale getirildi.
- Sağ panel aç/kapat davranışı korundu, localStorage anahtarı yenilendi ve varsayılan açık başlatıldı.
- Sayfa ölçüleri, görsel oranları, başlık fontları ve boşluklar referans görünüme göre yeniden ayarlandı.
- Cache karışmasını önlemek için index asset versiyonu yenilendi.

## Korunanlar

- E-Gazete gerçek gazete yaprağı hissi.
- Kişisel haber + trend + kaynak haberleri akışı.
- PDF indir butonu.
- Sağdaki kaynak paneli.
- Kategori sekmeleri.
- Haber detay açma davranışı.
- Backend, database.py ve main.py.
