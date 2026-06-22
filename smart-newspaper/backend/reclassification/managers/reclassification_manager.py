"""Business logic for admin reclassification, feedback, and retraining."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import hashlib
import math
import secrets
from typing import Any

from backend.reclassification.models.enums import (
    ACCURACY_DROP_TOLERANCE,
    ALLOWED_CATEGORY_VALUES,
    ROLE_PERMISSIONS,
    RETRAINING_TRIGGERS,
)
from backend.reclassification.models.schemas import AdminCorrectionStats, FeedbackQueueStatus, ReclassifyRequest


@dataclass
class Article:
    """Minimal article representation required by the feedback loop."""

    id: str
    title: str
    content: str = ""
    labels: list[str] = field(default_factory=list)
    category: str | None = None
    category_confidence: float = 0.0
    model_name: str = "auto-classifier"
    cluster_id: str | None = None
    language: str = "tr"


@dataclass
class AdminUserState:
    """Runtime-safe admin object used by the manager."""

    id: int
    username: str
    role: str
    email: str = ""
    is_active: bool = True
    total_corrections: int = 0
    accuracy_rate: float = 1.0
    failed_login_attempts: int = 0
    locked_until: datetime | None = None


@dataclass
class ReclassificationRecordState:
    """Stored correction record."""

    id: int
    article_id: str
    original_labels: list[str]
    original_model: str
    original_confidence: float
    corrected_labels: list[str]
    correction_reason: str | None
    admin_id: int
    admin_username: str
    corrected_at: datetime
    feedback_status: str
    feedback_weight: float
    verified_by: int | None = None
    verified_at: datetime | None = None
    is_verified: bool = False
    requires_verification: bool = False


@dataclass
class TrainingExample:
    """Training row produced from admin feedback."""

    article_id: str
    title: str
    content: str
    labels: list[str]
    label_vector: list[int]
    language: str
    is_augmented: bool
    labeled_at: datetime
    source: str
    weight: float


@dataclass
class FeedbackAnalysis:
    """Aggregate analysis of recent feedback quality."""

    total_corrections: int
    corrections_per_category: dict[str, int]
    most_confused_pairs: list[tuple[str, str, int]]
    admin_agreement_rate: float
    cohen_kappa: float
    retraining_recommended: bool
    recommended_at: datetime


@dataclass
class RetrainingTrigger:
    """Retraining trigger metadata."""

    trigger_id: str
    trigger_reason: str
    feedback_count: int
    triggered_at: datetime
    triggered_by: str
    status: str


@dataclass
class ModelMetadata:
    """Model version quality snapshot."""

    version: str
    accuracy: float
    created_at: datetime = field(default_factory=datetime.utcnow)


def labels_to_vector(labels: list[str]) -> list[int]:
    """Convert labels to a deterministic 9-dimensional multi-label vector."""
    selected = set(labels)
    return [1 if category in selected else 0 for category in ALLOWED_CATEGORY_VALUES]


class ReclassificationError(ValueError):
    """Domain error with an HTTP-like status code."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class ReclassificationManager:
    """Coordinates manual corrections, feedback queueing, and retraining gates.

    The manager is storage-agnostic and operates on in-memory dictionaries in
    tests/local mode. Production code can wrap the same methods with SQLAlchemy
    sessions and Celery tasks without changing validation behavior.
    """

    ALLOWED_CATEGORIES = dict(enumerate(ALLOWED_CATEGORY_VALUES))
    RETRAINING_THRESHOLD: int = int(RETRAINING_TRIGGERS["count_threshold"])
    DAILY_RATE_THRESHOLD: int = int(RETRAINING_TRIGGERS["daily_rate_threshold"])
    ACCURACY_THRESHOLD: float = float(RETRAINING_TRIGGERS["accuracy_threshold"])
    ACCURACY_DROP_TOLERANCE: float = ACCURACY_DROP_TOLERANCE
    MAX_RETRIES_CELERY: int = 3

    def __init__(self, db_session: Any | None = None, celery_app: Any | None = None, classifier: Any | None = None) -> None:
        self.db_session = db_session
        self.celery_app = celery_app
        self.classifier = classifier
        self.articles: dict[str, Article] = {}
        self.admins: dict[int, AdminUserState] = {}
        self.records: dict[int, ReclassificationRecordState] = {}
        self.training_examples: list[TrainingExample] = []
        self.triggers: dict[str, RetrainingTrigger] = {}
        self.dead_letter_queue: list[dict[str, Any]] = []
        self.security_log: list[dict[str, Any]] = []
        self.current_model = ModelMetadata(version="baseline", accuracy=0.86)
        self.old_model = self.current_model
        self._next_record_id = 1
        self._retraining_running = False

    def add_article(self, article: Article) -> None:
        """Add or replace an article in the manager store."""
        self.articles[article.id] = article

    def add_admin(self, admin: AdminUserState) -> None:
        """Add or replace an admin account in the manager store."""
        self.admins[admin.id] = admin

    def validate_correction(self, request: ReclassifyRequest, admin: AdminUserState) -> tuple[bool, str]:
        """Validate role, account state, daily limit, and label constraints."""
        if not admin.is_active:
            return False, "Admin pasif olduğu için işlem yapamaz."
        permissions = ROLE_PERMISSIONS.get(admin.role)
        if not permissions or not permissions.get("can_reclassify"):
            return False, "Bu işlem için reclassify yetkisi gerekli."
        if admin.total_corrections >= int(permissions["max_corrections_per_day"]):
            return False, "Günlük düzeltme limiti aşıldı."
        try:
            ReclassifyRequest.model_validate(request.model_dump())
        except Exception as exc:
            self.security_log.append({"event": "invalid_reclassification", "admin_id": admin.id, "detail": str(exc), "at": datetime.utcnow()})
            return False, str(exc)
        return True, "ok"

    def _needs_second_verification(self, article: Article, corrected_labels: list[str], admin: AdminUserState) -> bool:
        original_set = set(article.labels or ([article.category] if article.category else []))
        corrected_set = set(corrected_labels)
        return len(original_set & corrected_set) == 0 and admin.role == "reviewer"

    def _feedback_weight_for(self, admin: AdminUserState) -> float:
        try:
            return float(ROLE_PERMISSIONS.get(admin.role, {}).get("feedback_weight", 1.0))
        except Exception:
            return 1.0

    def save_correction(self, request: ReclassifyRequest, article: Article, admin: AdminUserState) -> ReclassificationRecordState:
        """Create or update a correction record for the same admin/article pair."""
        valid, message = self.validate_correction(request, admin)
        if not valid:
            status = 422 if "kategori" in message.lower() or "seçil" in message.lower() else 403
            raise ReclassificationError(message, status)
        if article.id not in self.articles:
            self.add_article(article)
        existing = next((record for record in self.records.values() if record.article_id == article.id and record.admin_id == admin.id), None)
        if existing:
            existing.corrected_labels = list(request.corrected_labels)
            existing.correction_reason = request.correction_reason
            existing.corrected_at = datetime.utcnow()
            existing.feedback_status = "pending"
            existing.requires_verification = self._needs_second_verification(article, request.corrected_labels, admin)
            return existing
        record = ReclassificationRecordState(
            id=self._next_record_id,
            article_id=article.id,
            original_labels=list(article.labels or ([article.category] if article.category else [])),
            original_model=article.model_name,
            original_confidence=float(article.category_confidence or 0.0),
            corrected_labels=list(request.corrected_labels),
            correction_reason=request.correction_reason,
            admin_id=admin.id,
            admin_username=admin.username,
            corrected_at=datetime.utcnow(),
            feedback_status="pending",
            feedback_weight=self._feedback_weight_for(admin),
            requires_verification=self._needs_second_verification(article, request.corrected_labels, admin),
        )
        self.records[record.id] = record
        self._next_record_id += 1
        admin.total_corrections += 1
        return record

    def verify_correction(self, record_id: int, approved: bool, verifier: AdminUserState) -> bool:
        """Second-admin verification for a correction."""
        permissions = ROLE_PERMISSIONS.get(verifier.role, {})
        if not permissions.get("can_verify"):
            raise ReclassificationError("Bu işlem için editor veya super_admin rolü gerekli.", 403)
        record = self.records.get(record_id)
        if not record:
            raise ReclassificationError("Düzeltme kaydı bulunamadı.", 404)
        if record.admin_id == verifier.id:
            raise ReclassificationError("Admin kendi yaptığı düzeltmeyi doğrulayamaz.", 403)
        if record.is_verified or record.feedback_status in {"processed", "rejected"}:
            raise ReclassificationError("Bu kayıt zaten doğrulanmış veya sonuçlandırılmış.", 409)
        if approved:
            record.is_verified = True
            record.verified_by = verifier.id
            record.verified_at = datetime.utcnow()
            record.feedback_status = "processed"
            record.feedback_weight = round(record.feedback_weight * 1.3, 4)
        else:
            record.feedback_status = "rejected"
        return True

    def process_feedback(self, record_id: int) -> bool:
        """Convert one correction into a training example."""
        record = self.records.get(record_id)
        if not record:
            self.dead_letter_queue.append({"record_id": record_id, "reason": "record_missing", "at": datetime.utcnow()})
            return False
        article = self.articles.get(record.article_id)
        if not article:
            record.feedback_status = "rejected"
            self.dead_letter_queue.append({"record_id": record_id, "reason": "orphan_article", "at": datetime.utcnow()})
            return False
        if record.requires_verification and not record.is_verified:
            return False
        example = TrainingExample(
            article_id=record.article_id,
            title=article.title,
            content=article.content,
            labels=list(record.corrected_labels),
            label_vector=labels_to_vector(record.corrected_labels),
            language=article.language,
            is_augmented=False,
            labeled_at=record.corrected_at,
            source="admin_correction",
            weight=record.feedback_weight,
        )
        self.training_examples.append(example)
        record.feedback_status = "processed"
        return True

    def analyze_feedback(self, days: int = 7) -> FeedbackAnalysis:
        """Analyze recent feedback distribution and agreement quality."""
        since = datetime.utcnow() - timedelta(days=days)
        recent = [record for record in self.records.values() if record.corrected_at >= since]
        per_category: Counter[str] = Counter()
        confusion: dict[str, Counter[str]] = defaultdict(Counter)
        article_to_label_sets: dict[str, list[set[str]]] = defaultdict(list)
        for record in recent:
            per_category.update(record.corrected_labels)
            article_to_label_sets[record.article_id].append(set(record.corrected_labels))
            for original in record.original_labels:
                for corrected in record.corrected_labels:
                    if original != corrected:
                        confusion[original][corrected] += 1
        confused_pairs = sorted(
            [(original, corrected, count) for original, dest in confusion.items() for corrected, count in dest.items()],
            key=lambda item: item[2],
            reverse=True,
        )[:10]
        comparable = [sets for sets in article_to_label_sets.values() if len(sets) > 1]
        agreements = sum(1 for sets in comparable if all(item == sets[0] for item in sets))
        agreement_rate = agreements / len(comparable) if comparable else 1.0
        # Lightweight kappa approximation for binary agreement over multi-label sets.
        expected = 1 / max(1, len(ALLOWED_CATEGORY_VALUES))
        kappa = (agreement_rate - expected) / (1 - expected) if agreement_rate < 1 else 1.0
        return FeedbackAnalysis(
            total_corrections=len(recent),
            corrections_per_category=dict(per_category),
            most_confused_pairs=confused_pairs,
            admin_agreement_rate=round(agreement_rate, 4),
            cohen_kappa=round(kappa, 4),
            retraining_recommended=len([r for r in self.records.values() if r.feedback_status == "processed"]) >= self.RETRAINING_THRESHOLD or kappa >= 0.6,
            recommended_at=datetime.utcnow(),
        )

    def build_weighted_dataset(self, feedback_records: list[ReclassificationRecordState]) -> list[TrainingExample]:
        """Build a weighted training dataset from correction records."""
        dataset: list[TrainingExample] = []
        for record in feedback_records:
            article = self.articles.get(record.article_id)
            if not article:
                continue
            copies = max(1, int(math.ceil(record.feedback_weight))) + (1 if record.is_verified else 0)
            for _ in range(copies):
                dataset.append(TrainingExample(
                    article_id=record.article_id,
                    title=article.title,
                    content=article.content,
                    labels=list(record.corrected_labels),
                    label_vector=labels_to_vector(record.corrected_labels),
                    language=article.language,
                    is_augmented=False,
                    labeled_at=record.corrected_at,
                    source="admin_correction",
                    weight=record.feedback_weight,
                ))
        return dataset

    def check_retraining_threshold(self) -> tuple[bool, str]:
        """Return whether model retraining should be queued."""
        if self._retraining_running:
            return False, "zaten çalışıyor"
        processed_count = sum(1 for record in self.records.values() if record.feedback_status == "processed")
        today = datetime.utcnow().date()
        today_count = sum(1 for record in self.records.values() if record.corrected_at.date() == today)
        if processed_count >= self.RETRAINING_THRESHOLD:
            return True, "threshold"
        if today_count >= self.DAILY_RATE_THRESHOLD:
            return True, "daily_rate"
        if self.current_model.accuracy <= self.ACCURACY_THRESHOLD:
            return True, "accuracy_drop"
        return False, "not_needed"

    def trigger_retraining(self, reason: str, triggered_by: str) -> RetrainingTrigger:
        """Create a retraining trigger unless one is already running."""
        if self._retraining_running:
            raise ReclassificationError("Retraining zaten çalışıyor.", 409)
        trigger_id = f"rt_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"
        trigger = RetrainingTrigger(
            trigger_id=trigger_id,
            trigger_reason=reason,
            feedback_count=sum(1 for record in self.records.values() if record.feedback_status == "processed"),
            triggered_at=datetime.utcnow(),
            triggered_by=triggered_by,
            status="queued",
        )
        self.triggers[trigger_id] = trigger
        return trigger

    def run_retraining(self, trigger_id: str) -> bool:
        """Simulate a guarded retraining run with rollback-on-regression."""
        trigger = self.triggers.get(trigger_id)
        if not trigger:
            raise ReclassificationError("Retraining tetikleyicisi bulunamadı.", 404)
        self._retraining_running = True
        trigger.status = "running"
        old_accuracy = self.current_model.accuracy
        processed = [record for record in self.records.values() if record.feedback_status == "processed"]
        dataset = self.build_weighted_dataset(processed)
        improvement = min(0.04, len(dataset) / 10000)
        new_accuracy = round(old_accuracy + improvement, 4)
        deployed, _ = self.evaluate_and_deploy(ModelMetadata(version=trigger_id, accuracy=new_accuracy), old_accuracy)
        if deployed:
            for record in processed:
                record.feedback_status = "used_in_training"
            trigger.status = "completed"
        else:
            trigger.status = "failed"
        self._retraining_running = False
        return deployed

    def evaluate_and_deploy(self, new_metadata: ModelMetadata, old_accuracy: float) -> tuple[bool, str]:
        """Deploy only when the new model is not materially worse."""
        if new_metadata.accuracy >= old_accuracy - self.ACCURACY_DROP_TOLERANCE:
            self.old_model = self.current_model
            self.current_model = new_metadata
            return True, "Yeni model kabul edildi."
        return False, "Yeni model doğruluğu toleransın altında kaldı; rollback yapıldı."

    def get_admin_stats(self, admin_id: int) -> AdminCorrectionStats:
        """Return per-admin correction counters."""
        admin = self.admins.get(admin_id)
        if not admin:
            raise ReclassificationError("Admin bulunamadı.", 404)
        records = [record for record in self.records.values() if record.admin_id == admin_id]
        today = datetime.utcnow().date()
        today_count = sum(1 for record in records if record.corrected_at.date() == today)
        labels = Counter(label for record in records for label in record.corrected_labels)
        first_date = min((record.corrected_at for record in records), default=datetime.utcnow())
        day_span = max(1, (datetime.utcnow().date() - first_date.date()).days + 1)
        return AdminCorrectionStats(
            admin_id=admin.id,
            username=admin.username,
            total_corrections=len(records),
            corrections_today=today_count,
            accuracy_rate=admin.accuracy_rate,
            most_corrected_category=labels.most_common(1)[0][0] if labels else "",
            avg_corrections_per_day=round(len(records) / day_span, 3),
        )

    def get_feedback_queue_status(self) -> FeedbackQueueStatus:
        """Return feedback queue counts and current threshold."""
        pending = sum(1 for record in self.records.values() if record.feedback_status == "pending")
        processed = sum(1 for record in self.records.values() if record.feedback_status == "processed")
        return FeedbackQueueStatus(
            pending_count=pending,
            processed_count=processed,
            retraining_threshold=self.RETRAINING_THRESHOLD,
            next_retraining_at=None,
            current_batch_id=1,
        )

    def get_confusion_analysis(self) -> dict[str, dict[str, int]]:
        """Return original-vs-corrected confusion matrix."""
        matrix: dict[str, dict[str, int]] = {category: {} for category in ALLOWED_CATEGORY_VALUES}
        for record in self.records.values():
            for original in record.original_labels:
                for corrected in record.corrected_labels:
                    if original != corrected:
                        matrix.setdefault(original, {})[corrected] = matrix.setdefault(original, {}).get(corrected, 0) + 1
        return matrix

    @staticmethod
    def stable_hash(value: str) -> str:
        """Return a deterministic short hash used by adapter layers."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def record_to_dict(record: ReclassificationRecordState) -> dict[str, Any]:
    """Serialize a correction record for API responses."""
    data = asdict(record)
    for key in ("corrected_at", "verified_at"):
        if data.get(key):
            data[key] = data[key].isoformat()
    return data
