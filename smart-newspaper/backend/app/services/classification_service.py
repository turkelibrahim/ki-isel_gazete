"""Application service for automatic news category classification."""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.classifiers.common import NB_MODEL_PATH, SVM_MODEL_PATH
from app.ml.classifiers.ensemble_classifier import ClassificationResult, EnsembleClassifier
from app.ml.classifiers.nb_classifier import NBClassifier
from app.ml.classifiers.svm_classifier import SVMClassifier
from app.ml.zero_shot_classifier import ZeroShotClassifier
from app.models import Article, ArticleCategory, Category, ModerationQueue

logger = logging.getLogger(__name__)
UNCERTAINTY_REVIEW_THRESHOLD = 0.65


DEFAULT_SEED_DATA: list[tuple[str, str]] = [
    ("Merkez Bankası faiz kararını açıkladı ve piyasalar enflasyon beklentilerini yeniden fiyatladı", "Ekonomi"),
    ("Borsa İstanbul gün içinde yükselirken dolar ve altın piyasalarında hareketlilik yaşandı", "Ekonomi"),
    ("Küresel petrol fiyatları ve döviz kuru şirket bilançolarını etkiliyor", "Ekonomi"),
    ("Takım derbide son dakikada attığı golle maçı kazandı ve liderliğe yükseldi", "Spor"),
    ("Milli takım Avrupa Şampiyonası elemelerinde kritik karşılaşmaya hazırlanıyor", "Spor"),
    ("Basketbol liginde play-off serisi büyük mücadeleye sahne oldu", "Spor"),
    ("Yapay zeka şirketi yeni dil modelini ve geliştirici araçlarını tanıttı", "Teknoloji"),
    ("Siber güvenlik uzmanları yeni veri sızıntısı hakkında kullanıcıları uyardı", "Teknoloji"),
    ("Akıllı telefon üreticisi kamera ve batarya özellikleri gelişmiş yeni modelini duyurdu", "Teknoloji"),
    ("Hükümet yeni düzenleme paketini meclise sundu ve muhalefet açıklama yaptı", "Gündem"),
    ("Bakanlık şehirlerde uygulanacak yeni kamu politikası için takvim paylaştı", "Gündem"),
    ("Yerel yönetimler ulaşım ve altyapı çalışmalarında yeni kararlar aldı", "Gündem"),
    ("Dünya liderleri zirvede savaş, diplomasi ve güvenlik konularını görüştü", "Dünya"),
    ("Birleşmiş Milletler kriz bölgesi için acil yardım çağrısı yaptı", "Dünya"),
    ("Avrupa ülkeleri göç ve enerji politikaları için ortak açıklama yayımladı", "Dünya"),
    ("Sağlık Bakanlığı yeni aşı kampanyası ve hastane kapasitesi hakkında bilgi verdi", "Sağlık"),
    ("Doktorlar mevsimsel salgınlara karşı hijyen ve erken teşhis uyarısı yaptı", "Sağlık"),
    ("Araştırmacılar kalp sağlığı ve beslenme alışkanlıkları üzerine yeni çalışma yayımladı", "Sağlık"),
    ("Üniversitelerde sınav takvimi ve kayıt yenileme süreci açıklandı", "Eğitim"),
    ("Milli Eğitim Bakanlığı müfredat değişikliği ve öğretmen atamaları hakkında duyuru yaptı", "Eğitim"),
    ("Öğrenciler burs başvuruları ve akademik takvim için yeni tarihleri bekliyor", "Eğitim"),
    ("Festival programında sinema, tiyatro ve konser etkinlikleri sanatseverlerle buluşacak", "Kültür"),
    ("Yeni sergi müze ziyaretçilerine çağdaş sanat eserlerini tanıtıyor", "Kültür"),
    ("Ünlü yazarın romanı edebiyat ödülüne aday gösterildi", "Kültür"),
]


def slugify(value: str) -> str:
    """Return a stable ASCII-ish slug for category names."""
    lowered = value.lower().strip()
    translations = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    lowered = lowered.translate(translations)
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "unknown"


def build_article_text(article: Article) -> str:
    """Combine title, optional summary and content slice for classification."""
    title = getattr(article, "title", "") or ""
    summary = getattr(article, "summary", "") or getattr(article, "description", "") or ""
    content = getattr(article, "content", "") or ""
    return f"{title} {summary} {content[:1000]}".strip()


async def classify_article(db: AsyncSession, article_id: int) -> dict[str, Any]:
    """Classify one article and persist its category assignment.

    The preferred path is NB/SVM ensemble classification.  When model files are
    missing or the ensemble raises an error, zero-shot NLI is used as fallback.
    Any result with confidence < 0.65 is sent to ``moderation_queue`` for human
    review using uncertainty sampling.
    """
    article = await db.get(Article, article_id)
    if article is None:
        raise ValueError(f"Article {article_id} not found")

    article_text = build_article_text(article)
    result = _predict_with_ensemble_or_zero_shot(article_text)
    if result.confidence < UNCERTAINTY_REVIEW_THRESHOLD:
        result.needs_review = True
        result.reason = result.reason or "confidence_lt_0_65"

    category = await get_or_create_category(db, result.category)

    assignment = await _upsert_article_category(db, article.id, category.id, result)
    if result.needs_review:
        await _enqueue_moderation(db, article.id, category.id, result)

    await db.commit()
    return {
        "article_id": article.id,
        "category_id": category.id,
        "category": category.name,
        "article_category_id": assignment.id,
        **result.to_dict(),
        "uncertainty_threshold": UNCERTAINTY_REVIEW_THRESHOLD,
    }


async def train_models(db: AsyncSession, training_items: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Train and save NB/SVM models from human labels or seed data.

    If explicit training items are not provided and there are not enough human
    labels yet, deterministic seed samples are used so the application has a
    working baseline classifier. Human labels can later replace this baseline.
    """
    texts: list[str]
    labels: list[str]

    if training_items:
        texts = [str(item.get("text", "")).strip() for item in training_items]
        labels = [str(item.get("label", "")).strip() for item in training_items]
        pairs = [(text, label) for text, label in zip(texts, labels, strict=False) if text and label]
    else:
        pairs = await _load_human_training_pairs(db)
        if len(pairs) < 50:
            logger.info("Human labels below threshold, using deterministic seed dataset for baseline training")
            pairs = DEFAULT_SEED_DATA

    _validate_training_pairs(pairs)
    texts = [text for text, _label in pairs]
    labels = [label for _text, label in pairs]

    for label in sorted(set(labels)):
        await get_or_create_category(db, label)
    await db.commit()

    nb = NBClassifier()
    nb.fit(texts, labels)
    nb.save(NB_MODEL_PATH)

    svm = SVMClassifier()
    svm.fit(texts, labels)
    svm.save(SVM_MODEL_PATH)

    label_counts = dict(Counter(labels))
    return {
        "trained": True,
        "samples": len(texts),
        "labels": sorted(label_counts.keys()),
        "label_counts": label_counts,
        "models": {"nb": NB_MODEL_PATH, "svm": SVM_MODEL_PATH},
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


async def classify_batch(db: AsyncSession, limit: int = 50) -> dict[str, Any]:
    """Classify articles that do not yet have an automatic category assignment."""
    stmt = (
        select(Article)
        .outerjoin(ArticleCategory, Article.id == ArticleCategory.article_id)
        .where(ArticleCategory.id.is_(None))
        .order_by(Article.created_at.desc())
        .limit(limit)
    )
    articles = list((await db.execute(stmt)).scalars().all())
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for article in articles:
        try:
            results.append(await classify_article(db, article.id))
        except Exception as exc:  # pragma: no cover - defensive batch isolation
            logger.exception("Batch classification failed article_id=%s", article.id)
            await db.rollback()
            errors.append({"article_id": article.id, "error": str(exc)})

    return {"processed": len(results), "errors": len(errors), "items": results, "error_items": errors}


def get_model_status() -> dict[str, Any]:
    """Return local model file availability and metadata."""
    return {
        "nb": _model_file_status(NB_MODEL_PATH),
        "svm": _model_file_status(SVM_MODEL_PATH),
        "ensemble_ready": Path(NB_MODEL_PATH).exists() and Path(SVM_MODEL_PATH).exists(),
        "decision_policy": {
            "svm_direct_accept_threshold": 0.85,
            "low_confidence_cross_check": "Naive Bayes",
            "disagreement_target": "moderation_queue",
            "uncertainty_review_threshold": UNCERTAINTY_REVIEW_THRESHOLD,
            "zero_shot_fallback": "facebook/bart-large-mnli",
        },
    }


async def get_or_create_category(db: AsyncSession, name: str) -> Category:
    """Fetch a category by name or create it if missing."""
    clean_name = name.strip() or "Bilinmeyen"
    stmt = select(Category).where(Category.name == clean_name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    category = Category(name=clean_name, slug=slugify(clean_name))
    db.add(category)
    await db.flush()
    return category


async def _upsert_article_category(
    db: AsyncSession, article_id: int, category_id: int, result: ClassificationResult
) -> ArticleCategory:
    """Create or update an automatic category assignment."""
    stmt = select(ArticleCategory).where(
        ArticleCategory.article_id == article_id,
        ArticleCategory.category_id == category_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.confidence = result.confidence
        existing.model = result.model
        existing.is_human_label = False
        return existing

    assignment = ArticleCategory(
        article_id=article_id,
        category_id=category_id,
        confidence=result.confidence,
        model=result.model,
        is_human_label=False,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def _enqueue_moderation(
    db: AsyncSession, article_id: int, category_id: int, result: ClassificationResult
) -> None:
    """Insert one pending moderation item unless the article already has one."""
    stmt = select(ModerationQueue).where(
        ModerationQueue.article_id == article_id,
        ModerationQueue.status == "pending",
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.predicted_category_id = category_id
        existing.confidence = result.confidence
        existing.reason = result.reason or "low_confidence"
        return

    db.add(
        ModerationQueue(
            article_id=article_id,
            predicted_category_id=category_id,
            confidence=result.confidence,
            reason=result.reason or "low_confidence",
            status="pending",
        )
    )


async def _load_human_training_pairs(db: AsyncSession) -> list[tuple[str, str]]:
    """Load human-labeled article texts for future retraining."""
    stmt = (
        select(Article, Category)
        .join(ArticleCategory, Article.id == ArticleCategory.article_id)
        .join(Category, Category.id == ArticleCategory.category_id)
        .where(ArticleCategory.is_human_label.is_(True))
    )
    rows = (await db.execute(stmt)).all()
    return [(build_article_text(article), category.name) for article, category in rows]


def _predict_with_ensemble_or_zero_shot(text: str) -> ClassificationResult:
    """Return an ensemble prediction or zero-shot fallback result."""
    classifier = EnsembleClassifier()
    try:
        if classifier.load_if_available():
            return classifier.predict(text)
        logger.warning("Classification model files missing, using zero-shot fallback")
    except Exception:
        logger.exception("Ensemble classification failed, using zero-shot fallback")

    zero_result = ZeroShotClassifier().predict(text, multi_label=False)
    label = str(zero_result.get("label") or "unknown")
    score = float(zero_result.get("score") or 0.0)
    model_name = str(zero_result.get("model") or "zero_shot")
    return ClassificationResult(
        category=label,
        confidence=score,
        model=model_name,
        needs_review=score < UNCERTAINTY_REVIEW_THRESHOLD,
        reason="zero_shot_fallback" if score >= UNCERTAINTY_REVIEW_THRESHOLD else "zero_shot_low_confidence",
    )


def _validate_training_pairs(pairs: list[tuple[str, str]]) -> None:
    """Validate that the data can support CalibratedClassifierCV(cv=3)."""
    cleaned = [(text, label) for text, label in pairs if text and label]
    counts = Counter(label for _text, label in cleaned)
    if len(counts) < 2:
        raise ValueError("At least two categories are required for classification training")
    too_small = {label: count for label, count in counts.items() if count < 3}
    if too_small:
        raise ValueError(f"SVM calibrated cv=3 requires at least 3 samples per category: {too_small}")


def _model_file_status(path: str) -> dict[str, Any]:
    """Return existence, size and mtime for one model file."""
    p = Path(path)
    if not p.exists():
        return {"exists": False, "path": path}
    return {
        "exists": True,
        "path": path,
        "size_bytes": p.stat().st_size,
        "modified_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
    }
