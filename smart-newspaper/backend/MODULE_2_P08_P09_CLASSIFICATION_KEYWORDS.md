# Modül 2 — P08 Multi-Label Classification + P09 Keyword Extraction

## P08 Genel Akış

1. Haber `articles` tablosundan okunur.
2. `MultiLabelClassifier` haber metnini TF-IDF vektörüne çevirir.
3. Binary Relevance modeli her kategori için bağımsız olasılık üretir.
4. İsteğe bağlı 5 adet `ClassifierChain` kategori korelasyonlarını öğrenir.
5. Binary Relevance ve Chain olasılıkları ortalanır.
6. `threshold=0.40` üstündeki her kategori seçilir.
7. Her kategori `article_categories` tablosuna ayrı satır olarak kaydedilir.
8. Duplicate kategori satırı varsa güncellenir veya atlanır.

## P09 Genel Akış

1. Haber başlığı, özet alanı varsa özet ve `content[:1000]` birleştirilir.
2. `KeywordExtractor` üç algoritmayı çalıştırır:
   - TF-IDF
   - RAKE
   - YAKE
3. RAKE veya YAKE paketi kurulu değilse sistem çökmez; güvenli fallback kullanır.
4. Skorlar normalize edilir.
5. Ensemble skor hesaplanır:
   - TF-IDF: 0.40
   - RAKE: 0.30
   - YAKE: 0.30
6. En yüksek skorlu maksimum 15 keyword/phrase `article_keywords` tablosuna kaydedilir.

## Endpointler

```bash
POST /api/multilabel/train
POST /api/multilabel/articles/{article_id}/classify
POST /api/multilabel/batch
GET  /api/multilabel/status

POST /api/articles/{article_id}/keywords
POST /api/keywords/batch
GET  /api/articles/{article_id}/keywords
```

## Kurulum

```bash
pip install scikit-learn joblib
pip install rake-nltk yake nltk
```

## Doğrulama

- Bir haber birden fazla kategoriye atanabilir.
- Her kategori `article_categories` tablosuna ayrı satır olarak yazılır.
- `threshold=0.40` altında kalan kategoriler seçilmez.
- Model dosyası `models/multilabel.pkl` olarak kaydedilip yüklenebilir.
- Her haber için maksimum 15 keyword kaydedilir.
- Aynı keyword tekrar yazılmaz.
- Boş veya çok kısa metin sistemi çökertmez.
