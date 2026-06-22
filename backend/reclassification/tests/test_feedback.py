from __future__ import annotations

from backend.reclassification.managers.feedback_manager import FeedbackManager
from backend.reclassification.managers.reclassification_manager import AdminUserState, Article, ReclassificationManager
from backend.reclassification.models.schemas import ReclassifyRequest


def test_feedback_manager_processes_record() -> None:
    manager = ReclassificationManager()
    article = Article(id="a1", title="Spor haberi", content="maç gol lig", labels=["Spor"], category="Spor")
    admin = AdminUserState(id=1, username="editor", role="editor")
    manager.add_article(article)
    manager.add_admin(admin)
    record = manager.save_correction(ReclassifyRequest(article_id="a1", corrected_labels=["Spor"]), article, admin)
    feedback = FeedbackManager(manager)
    assert feedback.process_feedback(record.id) is True
    assert len(manager.training_examples) == 1
