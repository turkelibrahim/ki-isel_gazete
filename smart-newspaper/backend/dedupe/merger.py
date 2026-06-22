"""Cluster merging helpers for SmartNewspaper duplicate groups."""

from __future__ import annotations

import hashlib
import math
from collections import Counter

from .models import ClusteredNewsArticle, RawNewsArticle, SourceVersion
from .text_cleaner import normalize_text, tokenize


def source_trust(article: RawNewsArticle) -> float:
    """Return a bounded source trust score."""
    try:
        return max(0.0, min(100.0, float(article.trust_score)))
    except (TypeError, ValueError):
        return 50.0


def pick_main_article(articles: list[RawNewsArticle]) -> RawNewsArticle:
    """Pick the canonical article by trust score first, then earliest publication time."""
    if not articles:
        raise ValueError("Cluster cannot be empty")

    def sort_key(article: RawNewsArticle) -> tuple[float, float, str]:
        published = article.parsed_published_at
        timestamp = published.timestamp() if published else math.inf
        return (-source_trust(article), timestamp, article.id)

    return sorted(articles, key=sort_key)[0]


def _unique_sentence_delta(main_text: str, other_text: str) -> str:
    main_tokens = set(tokenize(main_text))
    sentences = [s.strip() for s in other_text.replace("!", ".").replace("?", ".").split(".")]
    selected: list[str] = []
    for sentence in sentences:
        if len(sentence) < 40:
            continue
        sentence_tokens = set(tokenize(sentence))
        if not sentence_tokens:
            continue
        overlap = len(sentence_tokens & main_tokens) / max(1, len(sentence_tokens))
        if overlap < 0.72:
            selected.append(sentence)
        if len(selected) == 2:
            break
    return ". ".join(selected)[:500]


def build_cluster_id(main: RawNewsArticle, articles: list[RawNewsArticle]) -> str:
    """Build a stable cluster id from canonical title, category and source urls."""
    seed = "|".join(
        [
            normalize_text(main.title)[:120],
            main.category,
            "|".join(sorted(a.source_url or a.url or a.id for a in articles)),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    date = (main.published_at or "unknown")[:10].replace("-", "_") or "unknown"
    category = normalize_text(main.category or "gundem").replace(" ", "_") or "gundem"
    return f"cluster_{date}_{category}_{digest}"


def build_additional_source_info(main: RawNewsArticle, articles: list[RawNewsArticle]) -> list[dict[str, str]]:
    """Store useful extra information from non-main sources without dropping URLs."""
    main_text = f"{main.title}. {main.summary}. {main.content}"
    info: list[dict[str, str]] = []
    for article in articles:
        if article.id == main.id:
            continue
        extra = _unique_sentence_delta(main_text, f"{article.summary}. {article.content}")
        if extra:
            info.append(
                {
                    "source_name": article.source_name,
                    "source_url": article.source_url or article.url,
                    "detail": extra,
                }
            )
    return info


def dedupe_source_versions(sources: list[SourceVersion]) -> list[SourceVersion]:
    """Remove repeated source rows while preserving every distinct source URL."""
    seen: set[tuple[str, str]] = set()
    output: list[SourceVersion] = []
    for source in sources:
        key = (source.source_name.lower(), source.source_url)
        if key in seen:
            continue
        seen.add(key)
        output.append(source)
    return output


def merge_articles(
    articles: list[RawNewsArticle],
    *,
    pair_scores: dict[tuple[int, int], float],
    index_lookup: dict[str, int],
) -> ClusteredNewsArticle:
    """Merge a group of duplicate articles into one canonical cluster payload."""
    main = pick_main_article(articles)
    source_versions: list[SourceVersion] = []
    max_score = 0.0
    for article in sorted(articles, key=lambda item: (item.parsed_published_at is None, item.parsed_published_at or main.parsed_published_at, item.source_name)):
        left = index_lookup.get(main.id, -1)
        right = index_lookup.get(article.id, -1)
        key = tuple(sorted((left, right)))
        score = 1.0 if article.id == main.id else pair_scores.get(key, 0.85)
        max_score = max(max_score, score if article.id != main.id else 0.0)
        status = "main" if article.id == main.id else ("discarded" if score >= 0.95 else "merged")
        extra = "" if article.id == main.id else _unique_sentence_delta(f"{main.summary}. {main.content}", f"{article.summary}. {article.content}")
        source_versions.append(
            SourceVersion.from_article(
                article,
                duplicate_score=score,
                dedupe_status=status,
                additional_info=extra,
            )
        )
    source_versions = dedupe_source_versions(source_versions)
    if len(source_versions) <= 1:
        cluster_status = "unique"
        max_score = 0.0
    else:
        non_main_statuses = [source.dedupe_status for source in source_versions if source.dedupe_status != "main"]
        cluster_status = "discarded" if non_main_statuses and all(status == "discarded" for status in non_main_statuses) else "merged"
    return ClusteredNewsArticle(
        cluster_id=build_cluster_id(main, articles),
        main_article=main,
        sources=source_versions,
        duplicate_score=round(max_score, 4),
        dedupe_status=cluster_status,
        additional_source_info=build_additional_source_info(main, articles),
    )
