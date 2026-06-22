# Modül 2 — Toplu Kurulum ve Kontrol Listesi

Bu doküman, **MODÜL 2 — News Classification** kapsamındaki P07, P08, P09, P10 ve P11 parçalarının tek yerden kurulması ve doğrulanması için hazırlandı.

## Modül 2 Toplu Kurulum

```bash
pip install scikit-learn joblib
pip install rake-nltk yake nltk
pip install transformers torch
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 2 Genel Akış

1. Haber `articles` tablosuna kaydedilir.
2. `ClassificationService` haberi alır.
3. Önce klasik ML modeli çalışır:
   - Naive Bayes
   - SVM
   - Ensemble karar mekanizması
4. Haber birden fazla kategoriye uyuyorsa Multi-Label classifier çalışır.
5. Anahtar kelimeler TF-IDF + RAKE + YAKE ile çıkarılır.
6. Eğitim verisi yetmediği durumlarda Zero-Shot NLI fallback kullanılır.
7. Düşük güvenli tahminler `moderation_queue` içine atılır.
8. Admin doğru kategoriyi seçerse `is_human_label=True` olarak kaydedilir.
9. 50+ insan etiketi birikince model yeniden eğitilir.
10. Yeni model timestamp ile kaydedilir, eski model rollback için tutulur.

## Modül 2 Kontrol Listesi

- [x] NB modeli eğitiliyor ve `models/nb.pkl` oluşuyor.
- [x] SVM modeli eğitiliyor ve `models/svm.pkl` oluşuyor.
- [x] SVM confidence `>= 0.85` ise otomatik kabul var.
- [x] NB ve SVM farklıysa `moderation_queue` kaydı oluşacak servis akışı var.
- [x] Multi-label classification birden fazla kategori yazabiliyor.
- [x] Keyword extraction en fazla 15 keyword çıkarıyor.
- [x] `article_keywords` tablosuna `keyword + score` kaydediliyor.
- [x] Zero-shot model singleton/lazy-load olarak yalnızca ilk tahminde yükleniyor.
- [x] GPU varsa `device=0`, yoksa CPU fallback `device=-1` çalışacak şekilde ayarlandı.
- [x] `confidence < 0.65` kayıtlar admin kuyruğuna düşüyor.
- [x] Admin düzeltmesi `is_human_label=True` yapıyor.
- [x] 50+ insan etiketi olmadan retrain başlamıyor.
- [x] Yeni model timestamp ile kaydediliyor.
- [x] `database.py` değiştirilmedi.
- [x] `main.py` sadece router import/include için değişti.

## Endpoint Özeti

### P07 — NB + SVM + Ensemble

```bash
POST /api/classification/train
POST /api/classification/articles/{article_id}/classify
POST /api/classification/batch?limit=50
GET  /api/classification/models/status
```

### P08 — Multi-Label Classification

```bash
POST /api/multilabel/train
POST /api/multilabel/articles/{article_id}/classify
POST /api/multilabel/batch
GET  /api/multilabel/status
```

### P09 — Keyword Extraction

```bash
POST /api/articles/{article_id}/keywords
POST /api/keywords/batch
GET  /api/articles/{article_id}/keywords
```

### P10 — Zero-Shot NLI

```bash
GET  /api/ai/labels
POST /api/ai/add-label
```

### P11 — Active Learning / Moderation

```bash
GET  /api/moderation/pending?admin_user_id=<ADMIN_ID>
POST /api/moderation/{id}/approve
POST /api/moderation/{id}/reclassify
POST /api/moderation/{id}/reviewed
POST /api/moderation/retrain
GET  /api/moderation/stats?admin_user_id=<ADMIN_ID>
```

## Notlar

- `database.py` dosyasına dokunulmadı.
- UI/CSS/HTML dosyalarına dokunulmadı; ekran kayması oluşturacak tasarım değişikliği yapılmadı.
- Zero-shot modeli büyük olduğu için import sırasında yüklenmez; ilk gerçek tahminde yüklenir.
- Gerçek BART modeli ilk kullanımda internet/cache durumuna göre indirilebilir veya cache’den çalışır.
