"""Configurable keyword rules for first-pass category classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

from .models import SUPPORTED_CATEGORIES
from .text_cleaner import normalize_text


CATEGORY_KEYWORDS: Dict[str, Dict[str, float]] = {
    "Spor": {
        "spor": 1.2, "futbol": 2.0, "basketbol": 2.0, "voleybol": 2.0, "süper lig": 2.2,
        "maç": 1.8, "gol": 1.6, "transfer": 1.6, "galatasaray": 2.0, "fenerbahçe": 2.0,
        "beşiktaş": 2.0, "trabzonspor": 2.0, "uefa": 1.8, "nba": 1.8, "champions league": 2.0,
    },
    "Ekonomi": {
        "ekonomi": 1.8, "dolar": 2.0, "euro": 1.8, "altın": 1.8, "borsa": 2.0,
        "bist": 2.2, "enflasyon": 2.2, "faiz": 1.8, "merkez bankası": 2.2, "piyasa": 1.5,
        "kredi": 1.4, "vergi": 1.5, "zam": 1.2, "maaş": 1.3, "petrol": 1.3, "kripto": 1.6,
        "market": 1.4, "stocks": 2.0, "inflation": 2.2, "central bank": 2.2, "economy": 1.8,
    },
    "Teknoloji": {
        "teknoloji": 1.8, "yapay zeka": 2.4, "ai": 1.4, "openai": 2.4, "chatgpt": 2.2,
        "gemini": 1.6, "claude": 1.4, "robot": 1.5, "yazılım": 1.8, "siber": 1.8,
        "uygulama": 1.2, "telefon": 1.2, "nvidia": 2.0, "chip": 1.5, "startup": 1.6,
        "artificial intelligence": 2.4, "software": 1.8, "cybersecurity": 2.0, "technology": 1.8,
    },
    "Siyaset": {
        "siyaset": 1.8, "seçim": 2.0, "parti": 1.5, "meclis": 1.8, "tbmm": 2.2,
        "cumhurbaşkanı": 2.0, "bakan": 1.5, "milletvekili": 1.8, "chp": 2.0, "ak parti": 2.0,
        "mhp": 1.8, "iyi parti": 1.8, "yasa teklifi": 2.2, "politics": 1.8, "election": 2.0,
        "parliament": 2.0, "president": 1.4, "government bill": 2.0,
    },
    "Gündem": {
        "gündem": 1.5, "son dakika": 1.2, "kaza": 1.8, "yangın": 1.6, "polis": 1.5,
        "jandarma": 1.5, "mahkeme": 1.4, "belediye": 1.4, "istanbul": 0.8, "ankara": 0.8,
        "izmir": 0.8, "türkiye": 0.7, "toplum": 1.1, "protesto": 1.4, "güvenlik": 1.2,
        "breaking": 1.0, "accident": 1.8, "court": 1.5, "local": 1.0,
    },
    "Sağlık": {
        "sağlık": 2.0, "hastane": 1.8, "doktor": 1.7, "hasta": 1.5, "ilaç": 1.6,
        "tedavi": 1.8, "ameliyat": 1.8, "aşı": 1.8, "virüs": 1.6, "kanser": 2.0,
        "health": 2.0, "hospital": 1.8, "doctor": 1.7, "vaccine": 1.8, "treatment": 1.8,
    },
    "Bilim": {
        "bilim": 2.0, "araştırma": 1.8, "uzay": 2.0, "nasa": 2.2, "iklim": 1.8,
        "keşif": 1.6, "fosil": 1.7, "deney": 1.5, "deprem araştırması": 1.8, "science": 2.0,
        "research": 1.8, "space": 2.0, "climate": 1.8, "discovery": 1.6,
    },
    "Dünya": {
        "dünya": 1.4, "abd": 1.5, "avrupa": 1.3, "rusya": 1.5, "ukrayna": 1.6,
        "iran": 1.4, "israil": 1.5, "gazze": 1.8, "filistin": 1.8, "çin": 1.4,
        "almanya": 1.2, "fransa": 1.2, "nato": 1.6, "bm": 1.6, "united nations": 1.8,
        "world": 1.5, "global": 1.2, "war": 1.5, "foreign": 1.4, "international": 1.6,
    },
    "Yaşam": {
        "yaşam": 1.7, "aile": 1.4, "eğitim": 1.6, "okul": 1.4, "öğrenci": 1.4,
        "seyahat": 1.5, "turizm": 1.5, "moda": 1.4, "yemek": 1.5, "tarif": 1.5,
        "life": 1.6, "travel": 1.5, "education": 1.5, "school": 1.4, "lifestyle": 1.7,
    },
    "Kültür/Sanat": {
        "kültür": 1.8, "sanat": 1.8, "sinema": 1.8, "film": 1.5, "tiyatro": 2.0,
        "kitap": 1.8, "sergi": 1.8, "müze": 1.6, "konser": 1.4, "festival": 1.4,
        "culture": 1.8, "art": 1.8, "cinema": 1.8, "theatre": 1.8, "book": 1.6,
    },
    "Eğlence": {
        "eğlence": 1.8, "magazin": 2.0, "ünlü": 1.6, "dizi": 1.7, "yarışma": 1.5,
        "televizyon": 1.5, "oyun": 1.4, "game": 1.4, "celebrity": 2.0, "entertainment": 1.8,
        "series": 1.5, "streaming": 1.4,
    },
    "Diğer": {},
}

CATEGORY_ALIASES = {
    "Kültür-Sanat": "Kültür/Sanat",
    "Kültür Sanat": "Kültür/Sanat",
    "Kultur Sanat": "Kültür/Sanat",
    "Finans": "Ekonomi",
    "Eğitim": "Yaşam",
    "Dunya": "Dünya",
    "Gundem": "Gündem",
    "Politika": "Siyaset",
    "Technology": "Teknoloji",
    "Economy": "Ekonomi",
    "Sports": "Spor",
    "Health": "Sağlık",
    "Science": "Bilim",
    "World": "Dünya",
    "Other": "Diğer",
}


@dataclass(frozen=True)
class RuleMatch:
    """Keyword rule result before ML fallback."""

    category: str
    confidence: float
    matched_keywords: List[str]
    scores: Dict[str, float]


def normalize_category(value: str) -> str:
    """Normalize legacy category names into the supported category config."""

    raw = str(value or "").strip()
    if not raw:
        return "Diğer"
    if raw in SUPPORTED_CATEGORIES:
        return raw
    alias = CATEGORY_ALIASES.get(raw) or CATEGORY_ALIASES.get(raw.replace("/", "-").replace("  ", " "))
    return alias if alias in SUPPORTED_CATEGORIES else "Diğer"


def score_keywords(text: str, keywords: Mapping[str, float]) -> Tuple[float, List[str]]:
    """Score normalized keyword/phrase hits in article text."""

    normalized = normalize_text(text)
    score = 0.0
    hits: List[str] = []
    for keyword, weight in keywords.items():
      normalized_keyword = normalize_text(keyword)
      if not normalized_keyword:
          continue
      is_phrase = " " in normalized_keyword
      found = normalized_keyword in normalized if is_phrase else f" {normalized} ".find(f" {normalized_keyword} ") >= 0
      if found:
          score += float(weight)
          hits.append(keyword)
    return score, hits


def classify_with_rules(text: str) -> RuleMatch:
    """Run high-precision keyword rules and return a confidence score."""

    category_scores: Dict[str, float] = {}
    category_hits: Dict[str, List[str]] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "Diğer":
            continue
        score, hits = score_keywords(text, keywords)
        category_scores[category] = score
        category_hits[category] = hits

    ordered = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)
    if not ordered or ordered[0][1] <= 0:
        return RuleMatch("Diğer", 0.0, [], category_scores)

    best_category, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    hit_count = len(category_hits.get(best_category, []))
    margin = max(0.0, best_score - second_score)
    confidence = 0.45 + min(0.30, best_score / 12.0) + min(0.20, margin / 7.0) + min(0.08, hit_count * 0.015)
    confidence = max(0.0, min(0.98, confidence))

    # Politics and general agenda overlap a lot; require a political signal for Siyaset.
    if best_category == "Siyaset" and best_score < 2.8:
        confidence = min(confidence, 0.74)
    if best_category == "Gündem" and second_score >= best_score * 0.85:
        confidence = min(confidence, 0.78)

    return RuleMatch(best_category, confidence, category_hits.get(best_category, []), category_scores)
