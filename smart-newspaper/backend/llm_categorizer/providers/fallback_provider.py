"""Rule-based fallback provider for constrained categorization."""
from __future__ import annotations

import json
import re
import time
from collections import Counter

from backend.llm_categorizer.models import ALLOWED_CATEGORY_NAMES, LLMOutputSchema, ProviderResult

KEYWORD_RULES: dict[str, tuple[str, ...]] = {
    "Teknoloji": (
        "yapay zeka", "yazılım", "uygulama", "internet", "dijital", "teknoloji", "robot",
        "algoritma", "siber", "veri", "gpu", "çip", "api", "openai", "chatgpt", "software",
        "artificial intelligence", "cyber", "chip", "startup", "nvidia",
    ),
    "Siyaset": (
        "meclis", "hükümet", "seçim", "parti", "cumhurbaşkanı", "bakan", "kanun", "muhalefet",
        "koalisyon", "parlamento", "politics", "election", "minister", "government", "parliament",
        "president", "senate", "congress",
    ),
    "Spor": (
        "maç", "gol", "şampiyon", "turnuva", "futbol", "basketbol", "transfer", "stadyum",
        "antrenman", "lig", "football", "basketball", "match", "goal", "league", "nba", "uefa",
    ),
    "Ekonomi": (
        "faiz", "enflasyon", "dolar", "borsa", "bütçe", "ihracat", "yatırım", "banka", "piyasa",
        "gelir", "merkez bankası", "ekonomi", "market", "stocks", "inflation", "central bank",
        "interest rate", "investment", "finance",
    ),
    "Eğlence": (
        "film", "müzik", "konser", "dizi", "sanatçı", "oyuncu", "ödül", "festival", "sinema",
        "albüm", "celebrity", "entertainment", "series", "streaming", "actor", "music",
    ),
    "Sağlık": (
        "hastalık", "tedavi", "hastane", "ilaç", "doktor", "sağlık", "aşı", "pandemi", "ameliyat",
        "klinik", "health", "hospital", "doctor", "vaccine", "treatment", "medicine", "cancer",
    ),
    "Bilim": (
        "araştırma", "keşif", "uzay", "deney", "bilim", "nasa", "evren", "kimya", "fizik",
        "biyoloji", "science", "research", "space", "discovery", "scientists", "climate", "experiment",
    ),
    "Dünya": (
        "uluslararası", "küresel", "nato", "ab", "savaş", "ülke", "dışişleri", "göç",
        "birleşmiş milletler", "yabancı", "world", "global", "war", "foreign", "international",
        "united nations", "europe", "russia", "china", "gaza", "israel", "ukraine",
    ),
    "Yaşam": (
        "yemek", "seyahat", "aile", "eğitim", "kültür", "moda", "sağlıklı yaşam", "ilişki",
        "hobi", "tatil", "life", "travel", "education", "school", "lifestyle", "food", "family",
    ),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zçğıöşüâîû\s]+", " ", text.lower(), flags=re.IGNORECASE)).strip()


def _keyword_hits(text: str, keyword: str) -> int:
    normalized_text = _normalize(text)
    normalized_keyword = _normalize(keyword)
    if not normalized_keyword:
        return 0
    if " " in normalized_keyword:
        return 1 if normalized_keyword in normalized_text else 0
    return len(re.findall(rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)", normalized_text))


def rule_based_output(title: str, summary: str | None, content: str | None) -> LLMOutputSchema:
    """Return conservative category predictions using keyword rules only."""
    text = f"{title or ''}\n{summary or ''}\n{(content or '')[:500]}"
    if len(_normalize(text)) < 20:
        return LLMOutputSchema(categories=[], confidences={}, reasoning="Metin boş veya çok kısa olduğu için güvenilir kategori bulunamadı.")
    counters: Counter[str] = Counter()
    matched_terms: dict[str, list[str]] = {category: [] for category in ALLOWED_CATEGORY_NAMES}
    for category, keywords in KEYWORD_RULES.items():
        for keyword in keywords:
            hits = _keyword_hits(text, keyword)
            if hits:
                counters[category] += hits
                matched_terms[category].append(keyword)
    selected: list[str] = []
    confidences: dict[str, float] = {}
    for category, count in counters.most_common():
        if count < 2:
            continue
        selected.append(category)
        confidences[category] = round(min(0.75, 0.45 + count * 0.08 + min(0.12, len(matched_terms[category]) * 0.02)), 3)
    if not selected:
        return LLMOutputSchema(categories=[], confidences={}, reasoning="İzinli kategoriler için yeterli anahtar kelime eşleşmesi bulunamadı.")
    return LLMOutputSchema(
        categories=selected[:3],
        confidences={category: confidences[category] for category in selected[:3]},
        reasoning="Kural tabanlı fallback, haber metnindeki güvenli anahtar kelime eşleşmelerine göre kategori önerdi.",
    )


class FallbackProvider:
    """Provider that never calls external APIs and always returns a safe response."""

    provider = "fallback"
    model_name = "rule-based-keyword-fallback"

    async def categorize(self, title: str, summary: str | None, content: str | None) -> ProviderResult:
        """Classify with keyword rules and return ProviderResult metadata."""
        started = time.perf_counter()
        output = rule_based_output(title, summary, content)
        raw = json.dumps(output.model_dump(), ensure_ascii=False)
        return ProviderResult(
            raw_response=raw,
            prompt_tokens=0,
            completion_tokens=0,
            response_time_ms=(time.perf_counter() - started) * 1000,
            provider=self.provider,
            model_name=self.model_name,
        )
