"""MinHash + LSH candidate generation with TF-IDF final scoring.

The detector is designed for RSS/API batches. It never deletes input articles;
it returns duplicate-free clusters where every source URL is preserved under
``sources`` so SmartNewspaper cards, e-gazete and PDF exports can render one
story with multiple source icons.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from difflib import SequenceMatcher
from typing import Iterable, Mapping, Any

from .hasher import article_content_hash, canonicalize_url, exact_article_hash
from .merger import merge_articles
from .models import ClusteredNewsArticle, RawNewsArticle
from .text_cleaner import normalize_text, normalize_title, shingle_tokens, tokenize
from .union_find import UnionFind


@dataclass(slots=True)
class DedupeConfig:
    """Configuration values for the duplicate detector."""

    duplicate_threshold: float = 0.85
    discard_threshold: float = 0.95
    minhash_permutations: int = 96
    lsh_bands: int = 24
    max_pairwise_fallback: int = 80
    same_title_content_veto: float = 0.55


class DuplicateDetector:
    """Detect exact and near-duplicate news articles in one batch."""

    def __init__(self, config: DedupeConfig | None = None) -> None:
        self.config = config or DedupeConfig()
        if self.config.minhash_permutations % self.config.lsh_bands != 0:
            raise ValueError("minhash_permutations must be divisible by lsh_bands")

    def detect_and_cluster(self, items: Iterable[RawNewsArticle | Mapping[str, Any]]) -> list[ClusteredNewsArticle]:
        """Return duplicate-free clusters for a batch of raw articles."""
        articles = [self._to_article(item, index) for index, item in enumerate(items)]
        if not articles:
            return []
        if len(articles) == 1:
            return [merge_articles([articles[0]], pair_scores={}, index_lookup={articles[0].id: 0})]

        uf = UnionFind(len(articles))
        pair_scores: dict[tuple[int, int], float] = {}
        self._union_exact_duplicates(articles, uf, pair_scores)

        candidates = self._build_lsh_candidates(articles)
        if len(articles) <= self.config.max_pairwise_fallback:
            candidates.update(combinations(range(len(articles)), 2))

        vectors = self._build_tfidf_vectors(articles)
        title_vectors = self._build_tfidf_vectors(articles, titles_only=True)
        content_vectors = self._build_tfidf_vectors(articles, content_only=True)
        for left, right in sorted(tuple(sorted(pair)) for pair in candidates):
            if uf.find(left) == uf.find(right):
                continue
            key = (left, right)
            if key in pair_scores and pair_scores[key] >= 1.0:
                continue
            score = self._combined_similarity(articles, vectors, title_vectors, content_vectors, left, right)
            if self._same_title_different_content_veto(articles[left], articles[right], content_vectors[left], content_vectors[right]):
                score = min(score, self.config.duplicate_threshold - 0.01)
            if score >= self.config.duplicate_threshold:
                uf.union(left, right)
                pair_scores[key] = max(pair_scores.get(key, 0.0), score)

        index_lookup = {article.id: index for index, article in enumerate(articles)}
        clusters: list[ClusteredNewsArticle] = []
        for indexes in uf.groups().values():
            group_articles = [articles[index] for index in indexes]
            clusters.append(merge_articles(group_articles, pair_scores=pair_scores, index_lookup=index_lookup))
        return sorted(clusters, key=lambda cluster: (cluster.main_article.parsed_published_at is None, cluster.main_article.parsed_published_at or math.inf))

    def to_payload(self, items: Iterable[RawNewsArticle | Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Return API-ready payload dictionaries for clustered articles."""
        return [cluster.to_payload() for cluster in self.detect_and_cluster(items)]

    def _to_article(self, item: RawNewsArticle | Mapping[str, Any], index: int) -> RawNewsArticle:
        if isinstance(item, RawNewsArticle):
            if item.id:
                return item
            item.id = f"article_{index}"
            return item
        article = RawNewsArticle.from_mapping(item)
        if not article.id:
            article.id = f"article_{index}"
        article.source_url = canonicalize_url(article.source_url or article.url)
        return article

    def _union_exact_duplicates(self, articles: list[RawNewsArticle], uf: UnionFind, pair_scores: dict[tuple[int, int], float]) -> None:
        url_seen: dict[str, int] = {}
        exact_seen: dict[str, int] = {}
        content_seen: dict[str, int] = {}
        for index, article in enumerate(articles):
            url = canonicalize_url(article.source_url or article.url)
            exact = exact_article_hash(article.title, article.content, article.summary)
            content = article_content_hash(article.content, article.summary)
            for seen_map, key in ((url_seen, url), (exact_seen, exact), (content_seen, content)):
                if not key or key == article_content_hash("", ""):
                    continue
                if key in seen_map:
                    other = seen_map[key]
                    uf.union(other, index)
                    pair_scores[tuple(sorted((other, index)))] = 1.0
                else:
                    seen_map[key] = index

    def _build_lsh_candidates(self, articles: list[RawNewsArticle]) -> set[tuple[int, int]]:
        signatures = [self._minhash_signature(self._candidate_text(article)) for article in articles]
        rows = self.config.minhash_permutations // self.config.lsh_bands
        buckets: dict[tuple[int, tuple[int, ...]], list[int]] = defaultdict(list)
        for index, signature in enumerate(signatures):
            for band in range(self.config.lsh_bands):
                start = band * rows
                band_key = tuple(signature[start : start + rows])
                buckets[(band, band_key)].append(index)
        candidates: set[tuple[int, int]] = set()
        for bucket_indexes in buckets.values():
            if len(bucket_indexes) < 2:
                continue
            for left, right in combinations(bucket_indexes, 2):
                candidates.add(tuple(sorted((left, right))))
        return candidates

    def _candidate_text(self, article: RawNewsArticle) -> str:
        return " ".join([article.title, article.summary, article.content])

    def _minhash_signature(self, text: str) -> list[int]:
        shingles = shingle_tokens(text, n=3) or set(tokenize(text)) or {"__empty__"}
        signature: list[int] = []
        for seed in range(self.config.minhash_permutations):
            min_value = min(
                int(hashlib.blake2b(f"{seed}:{token}".encode("utf-8"), digest_size=8).hexdigest(), 16)
                for token in shingles
            )
            signature.append(min_value)
        return signature

    def _build_tfidf_vectors(
        self,
        articles: list[RawNewsArticle],
        *,
        titles_only: bool = False,
        content_only: bool = False,
    ) -> list[dict[str, float]]:
        docs: list[list[str]] = []
        for article in articles:
            if titles_only:
                text = normalize_title(article.title)
            elif content_only:
                text = normalize_text(article.content or article.summary)
            else:
                text = normalize_text(f"{article.title} {article.title} {article.summary} {article.content}")
            docs.append(tokenize(text))
        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        total_docs = max(1, len(docs))
        vectors: list[dict[str, float]] = []
        for tokens in docs:
            counts = Counter(tokens)
            vector: dict[str, float] = {}
            for token, count in counts.items():
                idf = math.log((total_docs + 1) / (df[token] + 1)) + 1.0
                vector[token] = (1.0 + math.log(count)) * idf
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            vectors.append({token: value / norm for token, value in vector.items()})
        return vectors

    def _cosine(self, left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(token, 0.0) for token, value in left.items())

    def _combined_similarity(
        self,
        articles: list[RawNewsArticle],
        vectors: list[dict[str, float]],
        title_vectors: list[dict[str, float]],
        content_vectors: list[dict[str, float]],
        left: int,
        right: int,
    ) -> float:
        combined = self._cosine(vectors[left], vectors[right])
        title = self._cosine(title_vectors[left], title_vectors[right])
        content = self._cosine(content_vectors[left], content_vectors[right])
        weighted = (0.28 * title) + (0.72 * content)
        lexical = self._lexical_similarity_score(articles[left], articles[right])
        score = max(combined, weighted, lexical)
        return round(min(1.0, max(0.0, score)), 4)

    def _lexical_similarity_score(self, left: RawNewsArticle, right: RawNewsArticle) -> float:
        """Boost near-identical rewrites using token coverage and character similarity."""
        left_text = normalize_text(f"{left.title} {left.summary} {left.content}")
        right_text = normalize_text(f"{right.title} {right.summary} {right.content}")
        left_tokens = set(tokenize(left_text))
        right_tokens = set(tokenize(right_text))
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = len(left_tokens & right_tokens)
        coverage = overlap / max(1, min(len(left_tokens), len(right_tokens)))
        jaccard = overlap / max(1, len(left_tokens | right_tokens))
        sequence = SequenceMatcher(None, left_text, right_text).ratio()
        title_tokens_left = set(tokenize(left.title))
        title_tokens_right = set(tokenize(right.title))
        title_coverage = len(title_tokens_left & title_tokens_right) / max(1, min(len(title_tokens_left), len(title_tokens_right)))
        if coverage >= 0.84:
            return min(0.97, 0.86 + (coverage - 0.84) * 0.45 + max(0.0, sequence - 0.45) * 0.08)
        if coverage >= 0.68 and title_coverage >= 0.45:
            return min(0.93, 0.85 + (coverage - 0.68) * 0.30 + max(0.0, sequence - 0.45) * 0.08)
        return (0.52 * coverage) + (0.28 * sequence) + (0.2 * jaccard)

    def _same_title_different_content_veto(
        self,
        left: RawNewsArticle,
        right: RawNewsArticle,
        left_content_vector: dict[str, float],
        right_content_vector: dict[str, float],
    ) -> bool:
        if normalize_title(left.title) != normalize_title(right.title):
            return False
        left_tokens = tokenize(left.content or left.summary)
        right_tokens = tokenize(right.content or right.summary)
        if min(len(left_tokens), len(right_tokens)) < 8:
            return False
        return self._cosine(left_content_vector, right_content_vector) < self.config.same_title_content_veto
