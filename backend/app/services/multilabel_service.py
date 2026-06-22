"""Service layer for multi-label article classification."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.classifiers.common import MULTILABEL_MODEL_PATH
from app.ml.classifiers.multilabel_classifier import CATEGORIES, MultiLabelClassifier, labels_to_matrix
from app.models import Article, ArticleCategory, Category
from app.services.classification_service import build_article_text, get_or_create_category

logger = logging.getLogger(__name__)

DEFAULT_MULTILABEL_SEED_DATA: list[tuple[str, list[str]]] = [
    ("Fenerbahçe transfer bütçesini ve sponsorluk gelirlerini açıkladı", ["Spor", "Ekonomi"]),
    ("Galatasaray maç gelirleri ve forma satışlarıyla yeni rekor kırdı", ["Spor", "Ekonomi"]),
    ("Basketbol kulübü dijital bilet ve mobil uygulama yatırımı yaptı", ["Spor", "Teknoloji"]),
    ("Merkez Bankası faiz kararını açıkladı ve piyasalar hareketlendi", ["Ekonomi", "Siyaset"]),
    ("Borsa İstanbul teknoloji hisseleriyle yükselişe geçti", ["Ekonomi", "Teknoloji"]),
    ("Petrol fiyatları dünya piyasalarında ve hükümet bütçesinde baskı yarattı", ["Ekonomi", "Dünya", "Siyaset"]),
    ("Yapay zeka şirketi sağlık teşhisi için yeni model geliştirdi", ["Teknoloji", "Sağlık"]),
    ("Siber güvenlik açığı okulların uzaktan eğitim sistemlerini etkiledi", ["Teknoloji", "Eğitim"]),
    ("Akıllı şehir projesi yerel yönetim ve teknoloji firmalarıyla başladı", ["Teknoloji", "Siyaset"]),
    ("Meclis sağlık çalışanları için yeni düzenleme teklifini görüştü", ["Siyaset", "Sağlık"]),
    ("Bakanlık eğitim müfredatı ve sınav sistemi için karar aldı", ["Siyaset", "Eğitim"]),
    ("Dünya liderleri iklim ve güvenlik zirvesinde ortak bildiri yayımladı", ["Siyaset", "Dünya"]),
    ("Hastanelerde dijital randevu ve yapay zeka destekli triyaj dönemi başladı", ["Sağlık", "Teknoloji"]),
    ("Doktorlar okul çağındaki çocuklar için aşı ve hijyen uyarısı yaptı", ["Sağlık", "Eğitim"]),
    ("Küresel salgın nedeniyle ülkeler yeni seyahat önlemleri aldı", ["Sağlık", "Dünya"]),
    ("Üniversite öğrencileri girişimcilik ve yazılım kampına katıldı", ["Eğitim", "Teknoloji"]),
    ("Milli Eğitim Bakanlığı kültür sanat dersleri için yeni program duyurdu", ["Eğitim", "Kültür"]),
    ("Yurt dışındaki öğrenciler için burs ve vize süreci açıklandı", ["Eğitim", "Dünya"]),
    ("Film festivali turizm geliri ve şehir ekonomisine katkı sağladı", ["Kültür", "Ekonomi"]),
    ("Müzede açılan bilim sergisi öğrencilere ücretsiz olacak", ["Kültür", "Eğitim"]),
    ("Uluslararası konser turnesi Avrupa şehirlerinde sanatseverlerle buluştu", ["Kültür", "Dünya"]),
    ("Avrupa futbol turnuvasında yayın teknolojileri ve sponsorluk gelirleri arttı", ["Spor", "Teknoloji", "Ekonomi"]),
    ("Dünya kupası güvenlik kararları ve ev sahibi ülke politikaları tartışıldı", ["Spor", "Dünya", "Siyaset"]),
    ("Sağlık teknolojileri fuarında eğitim seminerleri ve kültür etkinlikleri düzenlendi", ["Sağlık", "Teknoloji", "Eğitim", "Kültür"]),
]


async def train_multilabel_model(
    db: AsyncSession,
    training_items: list[dict[str, Any]] | None = None,
    use_classifier_chain: bool = True,
) -> dict[str, Any]:
    """Train and save the multi-label classifier from request data or seed data."""
    if training_items:
        pairs = _request_items_to_pairs(training_items)
    else:
        pairs = await _load_human_multilabel_pairs(db)
        if len(pairs) < 50:
            logger.info("Human multi-label data below threshold, using deterministic seed data")
            pairs = DEFAULT_MULTILABEL_SEED_DATA

    texts = [text for text, _labels in pairs]
    label_sets = [labels for _text, labels in pairs]
    matrix = labels_to_matrix(label_sets, CATEGORIES)

    for category_name in CATEGORIES:
        await get_or_create_category(db, category_name)
    await db.commit()

    classifier = MultiLabelClassifier()
    classifier.fit(texts, matrix, use_classifier_chain=use_classifier_chain)
    classifier.save(MULTILABEL_MODEL_PATH)

    counts = Counter(label for _text, labels in pairs for label in labels)
    return {
        "trained": True,
        "samples": len(texts),
        "categories": CATEGORIES,
        "label_counts": dict(counts),
        "threshold": classifier.threshold,
        "classifier_chains": len(classifier.chains),
        "model_path": MULTILABEL_MODEL_PATH,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


async def classify_multilabel_article(db: AsyncSession, article_id: int) -> dict[str, Any]:
    """Classify one article into zero or more categories and persist each row."""
    article = await db.get(Article, article_id)
    if article is None:
        raise ValueError(f"Article {article_id} not found")

    classifier = MultiLabelClassifier()
    if not classifier.load_if_available():
        raise RuntimeError("Multi-label model is not trained. Run POST /api/multilabel/train first.")

    predictions = classifier.predict(build_article_text(article))
    saved: list[dict[str, Any]] = []
    for prediction in predictions:
        category = await get_or_create_category(db, str(prediction["category"]))
        assignment = await _upsert_multilabel_category(
            db,
            article_id=article.id,
            category_id=category.id,
            confidence=float(prediction["confidence"]),
        )
        saved.append(
            {
                "article_category_id": assignment.id,
                "category_id": category.id,
                "category": category.name,
                "confidence": assignment.confidence,
            }
        )

    await db.commit()
    return {"article_id": article.id, "categories": saved, "count": len(saved), "threshold": classifier.threshold}


async def classify_multilabel_batch(db: AsyncSession, limit: int = 50) -> dict[str, Any]:
    """Run multi-label classification for a batch of recent articles."""
    stmt = select(Article).order_by(Article.created_at.desc()).limit(limit)
    articles = list((await db.execute(stmt)).scalars().all())
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for article in articles:
        try:
            results.append(await classify_multilabel_article(db, article.id))
        except Exception as exc:  # pragma: no cover - defensive batch isolation
            logger.exception("Multi-label batch failed article_id=%s", article.id)
            await db.rollback()
            errors.append({"article_id": article.id, "error": str(exc)})

    return {"processed": len(results), "errors": len(errors), "items": results, "error_items": errors}


def get_multilabel_status() -> dict[str, Any]:
    """Return model availability and policy metadata for multi-label classification."""
    path = Path(MULTILABEL_MODEL_PATH)
    status: dict[str, Any] = {
        "model_path": MULTILABEL_MODEL_PATH,
        "exists": path.exists(),
        "threshold": 0.40,
        "categories": CATEGORIES,
        "strategy": "Binary Relevance + optional 5-chain ClassifierChain average",
    }
    if path.exists():
        status.update(
            {
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return status


async def _upsert_multilabel_category(
    db: AsyncSession, article_id: int, category_id: int, confidence: float
) -> ArticleCategory:
    """Insert or update one article-category row for multi-label output."""
    stmt = select(ArticleCategory).where(
        ArticleCategory.article_id == article_id,
        ArticleCategory.category_id == category_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.confidence = confidence
        existing.model = "multilabel"
        existing.is_human_label = False
        return existing

    assignment = ArticleCategory(
        article_id=article_id,
        category_id=category_id,
        confidence=confidence,
        model="multilabel",
        is_human_label=False,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def _load_human_multilabel_pairs(db: AsyncSession) -> list[tuple[str, list[str]]]:
    """Load human-labeled article/category sets for future retraining."""
    stmt = (
        select(Article, Category)
        .join(ArticleCategory, Article.id == ArticleCategory.article_id)
        .join(Category, Category.id == ArticleCategory.category_id)
        .where(ArticleCategory.is_human_label.is_(True))
    )
    rows = (await db.execute(stmt)).all()
    grouped: dict[int, tuple[str, list[str]]] = {}
    for article, category in rows:
        if article.id not in grouped:
            grouped[article.id] = (build_article_text(article), [])
        grouped[article.id][1].append(category.name)
    return list(grouped.values())


def _request_items_to_pairs(items: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Normalize API training items into ``(text, labels)`` pairs."""
    pairs: list[tuple[str, list[str]]] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        labels_raw = item.get("labels", [])
        labels = [str(label).strip() for label in labels_raw if str(label).strip()]
        if text and labels:
            pairs.append((text, labels))
    if not pairs:
        raise ValueError("At least one training item with text and labels is required")
    return pairs
