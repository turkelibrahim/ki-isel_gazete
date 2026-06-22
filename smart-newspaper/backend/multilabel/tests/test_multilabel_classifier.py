from __future__ import annotations

from backend.multilabel.models import ALLOWED_LABELS
from backend.multilabel.multilabel_classifier import MultiLabelClassifier, classify_article, classify_articles
from backend.multilabel.output_validator import validate_prediction


def test_technology_and_economy_article_gets_two_labels() -> None:
    article = {
        "title": "OpenAI yapay zeka yatırımı için yeni API ve çip ortaklığını duyurdu",
        "summary": "Teknoloji şirketi finans piyasalarında yatırım ve borsa etkisi yarattı.",
        "content": "Yapay zeka, startup, yazılım, ekonomi, yatırım ve piyasa başlıkları öne çıktı.",
    }
    result = classify_article(article)
    assert "Teknoloji" in result["labels"]
    assert "Ekonomi" in result["labels"]
    assert result["label_vector"][ALLOWED_LABELS.index("Teknoloji")] == 1
    assert result["label_vector"][ALLOWED_LABELS.index("Ekonomi")] == 1
    assert result["num_labels"] == 9


def test_sports_article_gets_only_sports_label() -> None:
    article = {
        "title": "Galatasaray derbide Fenerbahçe karşısında üç golle kazandı",
        "summary": "Süper Lig maçında transfer ve futbol gündemi değişti.",
    }
    result = classify_article(article)
    assert result["labels"] == ["Spor"]


def test_no_threshold_pass_returns_empty_list() -> None:
    result = classify_article({"title": "Mahallede yeni düzenleme", "summary": "Kısa ve belirsiz bir haber metni."})
    assert result["labels"] == []
    assert result["no_label_detected"] is True
    assert result["fallback_category"] == "Diğer"


def test_forbidden_labels_are_never_generated() -> None:
    result = classify_article({"title": "Son dakika gündem genel bilinmeyen haber", "summary": "Diğer kategori üretilmemeli."})
    assert "Gündem" not in result["labels"]
    assert "Diğer" not in result["labels"]
    assert "Genel" not in result["labels"]
    assert "Bilinmeyen" not in result["labels"]
    assert set(result["label_scores"]) == set(ALLOWED_LABELS)


def test_unsupported_label_is_rejected_by_validator() -> None:
    prediction = validate_prediction({
        "labels": ["Teknoloji", "Gündem", "Genel"],
        "label_scores": {"Teknoloji": 0.91, "Gündem": 0.99},
        "is_multilabel_reliable": True,
    })
    assert prediction.labels == ["Teknoloji"]
    assert "Gündem" in prediction.rejected_labels
    assert "Genel" in prediction.rejected_labels
    assert prediction.label_vector == [1, 0, 0, 0, 0, 0, 0, 0, 0]


def test_batch_32_articles_can_be_processed() -> None:
    articles = [
        {"title": f"OpenAI yapay zeka yazılım haberi {index}", "summary": "Teknoloji ve API gelişmesi."}
        for index in range(32)
    ]
    results = classify_articles(articles)
    assert len(results) == 32
    assert all("Teknoloji" in item["labels"] for item in results)


def test_english_article_is_classified() -> None:
    result = classify_article({
        "title": "Central bank decision shakes technology stocks",
        "summary": "OpenAI and chip companies led the market after a new artificial intelligence investment.",
    })
    assert "Teknoloji" in result["labels"]
    assert "Ekonomi" in result["labels"]


def test_health_science_overlap() -> None:
    result = classify_article({
        "title": "Scientists publish vaccine research",
        "summary": "Health experts said the medicine study may improve cancer treatment.",
    })
    assert "Sağlık" in result["labels"]
    assert "Bilim" in result["labels"]


def test_empty_content_is_safe() -> None:
    result = MultiLabelClassifier().classify({}).to_dict()
    assert result["labels"] == []
    assert result["label_scores"] == {label: 0.0 for label in ALLOWED_LABELS}
    assert result["is_multilabel_reliable"] is False


def test_label_scores_are_independent_not_softmax() -> None:
    result = classify_article({
        "title": "OpenAI ekonomi piyasalarını etkiledi",
        "summary": "Yapay zeka yatırımı, teknoloji hisseleri, borsa ve merkez bankası kararları konuşuldu.",
    })
    assert result["label_scores"]["Teknoloji"] > 0.7
    assert result["label_scores"]["Ekonomi"] > 0.7
    assert sum(result["label_scores"].values()) > 1.0
