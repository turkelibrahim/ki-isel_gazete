from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.reclassification.managers.reclassification_manager import (
    ACCURACY_DROP_TOLERANCE,
    AdminUserState,
    Article,
    ModelMetadata,
    ReclassificationError,
    ReclassificationManager,
)
from backend.reclassification.models.schemas import ReclassifyRequest


def build_manager() -> ReclassificationManager:
    manager = ReclassificationManager()
    manager.add_article(Article(id="news_1", title="Yapay zeka çipi üretiminde rekor", content="Yapay zeka çip yatırımı borsayı etkiledi", labels=["Teknoloji"], category="Teknoloji", category_confidence=0.72))
    manager.add_admin(AdminUserState(id=1, username="reviewer", role="reviewer"))
    manager.add_admin(AdminUserState(id=2, username="editor", role="editor"))
    manager.add_admin(AdminUserState(id=3, username="root", role="super_admin"))
    return manager


def test_valid_reclassification_queues_feedback() -> None:
    manager = build_manager()
    record = manager.save_correction(
        ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji", "Ekonomi"], correction_reason="Ekonomi etkisi var"),
        manager.articles["news_1"],
        manager.admins[1],
    )
    assert record.feedback_status == "pending"
    assert record.corrected_labels == ["Teknoloji", "Ekonomi"]
    assert record.feedback_weight == 1.0


def test_invalid_category_rejected_and_not_saved() -> None:
    manager = build_manager()
    with pytest.raises(ValidationError):
        ReclassifyRequest(article_id="news_1", corrected_labels=["Gündem"])
    assert manager.records == {}


def test_duplicate_label_rejected() -> None:
    with pytest.raises(ValidationError):
        ReclassifyRequest(article_id="news_1", corrected_labels=["Spor", "Spor"])


def test_same_admin_same_article_updates_existing_record() -> None:
    manager = build_manager()
    request = ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji"])
    first = manager.save_correction(request, manager.articles["news_1"], manager.admins[1])
    second = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji", "Ekonomi"]), manager.articles["news_1"], manager.admins[1])
    assert first.id == second.id
    assert len(manager.records) == 1
    assert second.corrected_labels == ["Teknoloji", "Ekonomi"]


def test_admin_cannot_verify_own_record() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Ekonomi"]), manager.articles["news_1"], manager.admins[1])
    with pytest.raises(ReclassificationError) as exc:
        manager.verify_correction(record.id, True, manager.admins[1])
    assert exc.value.status_code == 403


def test_editor_can_verify_and_weight_increases() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Ekonomi"]), manager.articles["news_1"], manager.admins[1])
    assert record.requires_verification is True
    assert manager.verify_correction(record.id, True, manager.admins[2]) is True
    assert record.is_verified is True
    assert record.feedback_status == "processed"
    assert record.feedback_weight > 1.0


def test_process_feedback_creates_training_example() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji"]), manager.articles["news_1"], manager.admins[2])
    assert manager.process_feedback(record.id) is True
    assert manager.training_examples[0].label_vector == [1, 0, 0, 0, 0, 0, 0, 0, 0]
    assert record.feedback_status == "processed"


def test_orphan_feedback_is_rejected() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji"]), manager.articles["news_1"], manager.admins[2])
    manager.articles.pop("news_1")
    assert manager.process_feedback(record.id) is False
    assert record.feedback_status == "rejected"


def test_retraining_threshold_at_100_records() -> None:
    manager = build_manager()
    for i in range(100):
        article = Article(id=f"n{i}", title="Ekonomi haberi", content="faiz dolar borsa", labels=["Ekonomi"], category="Ekonomi")
        manager.add_article(article)
        record = manager.save_correction(ReclassifyRequest(article_id=article.id, corrected_labels=["Ekonomi"]), article, manager.admins[2])
        record.feedback_status = "processed"
    should_retrain, reason = manager.check_retraining_threshold()
    assert should_retrain is True
    assert reason == "threshold"


def test_model_rollback_when_accuracy_drop_exceeds_tolerance() -> None:
    manager = build_manager()
    deployed, message = manager.evaluate_and_deploy(ModelMetadata(version="bad", accuracy=manager.current_model.accuracy - ACCURACY_DROP_TOLERANCE - 0.01), manager.current_model.accuracy)
    assert deployed is False
    assert "rollback" in message.lower()
    assert manager.current_model.version == "baseline"


def test_weighted_dataset_duplicates_verified_feedback() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Teknoloji"]), manager.articles["news_1"], manager.admins[2])
    record.is_verified = True
    record.feedback_weight = 1.3
    dataset = manager.build_weighted_dataset([record])
    assert len(dataset) >= 3


def test_confusion_analysis_and_kappa_warning_path() -> None:
    manager = build_manager()
    record = manager.save_correction(ReclassifyRequest(article_id="news_1", corrected_labels=["Ekonomi"]), manager.articles["news_1"], manager.admins[1])
    matrix = manager.get_confusion_analysis()
    analysis = manager.analyze_feedback()
    assert matrix["Teknoloji"]["Ekonomi"] == 1
    assert analysis.total_corrections == 1
    assert analysis.cohen_kappa <= 1.0
