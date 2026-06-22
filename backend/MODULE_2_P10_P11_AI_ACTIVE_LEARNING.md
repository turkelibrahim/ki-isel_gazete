# Modül 2 — P10/P11 Zero-Shot NLI + Active Learning

## P10 — Zero-Shot NLI Classification

- `backend/app/ml/zero_shot_classifier.py` eklendi.
- `facebook/bart-large-mnli` modeli `transformers.pipeline("zero-shot-classification")` ile kullanılır.
- Model import anında yüklenmez; ilk gerçek tahmin isteğinde singleton olarak bir kez yüklenir.
- GPU varsa `device=0`, yoksa CPU için `device=-1` kullanılır.
- `hypothesis_template = "Bu metin {} hakkındadır."`
- Metin güvenli sınır için `text[:512]` ile sınırlanır.
- Model hata verirse sistem çökmez, SVM/NB ensemble fallback denenir.
- Yeni label eğitimsiz eklenebilir:
  - `POST /api/ai/add-label`
  - `GET /api/ai/labels`

## P11 — Active Learning + Manual Reclassification

- `confidence < 0.65` olan haberler `moderation_queue` içine düşer.
- Admin manuel kategori seçerse `article_categories.is_human_label=True` ve `confidence=1.0` olarak kaydedilir.
- Manuel düzeltmeler `audit_log` tablosuna `MANUAL_RECLASSIFICATION` olarak yazılır.
- `users.role = "ADMIN"` kontrolü yapılır; yetkisiz kullanıcı 403 alır.
- 50+ insan etiketi birikince retrain tetiklenebilir.
- Yeni modeller timestamp ile saklanır:
  - `models/nb_YYYYMMDD_HHMMSS.pkl`
  - `models/svm_YYYYMMDD_HHMMSS.pkl`
- Eski modeller silinmez; aktif alias olarak `models/nb.pkl` ve `models/svm.pkl` güncellenir.

## Endpointler

```bash
GET  /api/ai/labels
POST /api/ai/add-label

GET  /api/moderation/pending?admin_user_id=<ADMIN_ID>
POST /api/moderation/{id}/approve
POST /api/moderation/{id}/reclassify
POST /api/moderation/{id}/reviewed
POST /api/moderation/retrain
GET  /api/moderation/stats?admin_user_id=<ADMIN_ID>
```

## Kurulum

```bash
pip install transformers torch
pip install scikit-learn joblib
```

## Kontrol Listesi

- [ ] İlk zero-shot tahminde model yükleniyor mu?
- [ ] Sonraki tahminlerde model tekrar yüklenmiyor mu?
- [ ] GPU varsa device=0, yoksa CPU fallback çalışıyor mu?
- [ ] Yeni label eğitim yapmadan listeye ekleniyor mu?
- [ ] Ensemble model yoksa zero-shot fallback çalışıyor mu?
- [ ] confidence < 0.65 ise moderation_queue kaydı oluşuyor mu?
- [ ] Admin düzeltmesi is_human_label=True ve confidence=1.0 yazıyor mu?
- [ ] audit_log manuel düzeltmeyi saklıyor mu?
- [ ] 50 insan etiketi yoksa retrain başlamıyor mu?
- [ ] Retrain sonrası timestamp model dosyaları oluşuyor mu?
- [ ] database.py değişmedi mi?
