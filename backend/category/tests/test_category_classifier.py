from __future__ import annotations

from backend.category.category_classifier import CategoryClassifier
from backend.category.models import SUPPORTED_CATEGORIES


def article(title: str, summary: str = "", content: str = "", **extra):
    return {"title": title, "summary": summary, "content": content, **extra}


def test_spor_haberini_spor_yapar():
    pred = CategoryClassifier().classify(article(
        "Galatasaray derbide Fenerbahçe'yi mağlup etti",
        "Süper Lig maçında üç gol ve transfer açıklaması gündeme geldi."
    ))
    assert pred.category == "Spor"
    assert pred.is_category_reliable is True


def test_ekonomi_haberini_ekonomi_yapar():
    pred = CategoryClassifier().classify(article(
        "Merkez Bankası faiz kararını açıkladı",
        "Dolar, euro ve enflasyon beklentileri piyasada yakından izleniyor."
    ))
    assert pred.category == "Ekonomi"
    assert pred.category_confidence >= 0.85


def test_teknoloji_haberini_teknoloji_yapar():
    pred = CategoryClassifier().classify(article(
        "OpenAI yeni yapay zeka modelini tanıttı",
        "Yazılım geliştiricileri için ChatGPT ve API tarafında yeni teknoloji özellikleri açıklandı."
    ))
    assert pred.category == "Teknoloji"
    assert pred.is_category_reliable is True


def test_siyaset_gundem_ayrimi():
    classifier = CategoryClassifier()
    politics = classifier.classify(article(
        "TBMM'de yeni yasa teklifi görüşüldü",
        "Parti grupları ve milletvekilleri seçim sonrası düzenleme için mecliste açıklama yaptı."
    ))
    agenda = classifier.classify(article(
        "İstanbul'da zincirleme trafik kazası",
        "Polis ve belediye ekipleri bölgede güvenlik önlemi aldı."
    ))
    assert politics.category == "Siyaset"
    assert agenda.category == "Gündem"


def test_ingilizce_haberi_dogru_siniflandirir():
    pred = CategoryClassifier().classify(article(
        "Central bank holds interest rates as inflation cools",
        "Markets and stocks reacted after the economy report was published."
    ))
    assert pred.detected_lang == "en"
    assert pred.category == "Ekonomi"


def test_bos_icerikte_diger_doner():
    pred = CategoryClassifier().classify(article("", "", ""))
    assert pred.category == "Diğer"
    assert pred.category_source == "fallback"
    assert pred.is_category_reliable is False


def test_kisa_baslikta_dusuk_guven_doner():
    pred = CategoryClassifier().classify(article("Zam geldi"))
    assert pred.category == "Diğer"
    assert pred.category_confidence < 0.85
    assert pred.is_category_reliable is False


def test_batch_100_haber_siniflandirir():
    samples = [
        article(f"OpenAI yapay zeka platformu güncellendi {i}", "Yazılım ve teknoloji dünyasında yeni API duyuruldu.")
        for i in range(100)
    ]
    predictions = CategoryClassifier().classify_batch(samples)
    assert len(predictions) == 100
    assert all(pred.category in SUPPORTED_CATEGORIES for pred in predictions)
    assert predictions[0].category == "Teknoloji"


def test_payload_alanlari_uretilir():
    pred = CategoryClassifier().classify(article(
        "NASA yeni uzay keşfini duyurdu",
        "Bilim insanları araştırma sonuçlarını paylaştı."
    )).to_dict()
    assert pred["category"] == "Bilim"
    assert "category_confidence" in pred
    assert "category_source" in pred
    assert "is_category_reliable" in pred
    assert "detected_lang" in pred


def test_egazete_kategori_gruplamasi_calissin():
    classifier = CategoryClassifier()
    groups = classifier.group_by_category([
        article("Merkez Bankası faiz kararını açıkladı", "Dolar ve enflasyon piyasayı etkiledi."),
        article("Galatasaray transfer görüşmelerine başladı", "Süper Lig ekibi yeni futbolcu arıyor."),
        article("OpenAI yeni yapay zeka aracını yayınladı", "Teknoloji dünyasında yazılım geliştiricileri için yenilik."),
    ])
    assert "Ekonomi" in groups
    assert "Spor" in groups
    assert "Teknoloji" in groups
