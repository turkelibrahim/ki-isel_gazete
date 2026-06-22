"""Turkish NLP pipeline with optional spaCy and safe fallback."""
from __future__ import annotations

from . import generic

CUSTOM_TR_STOPWORDS = {
    "bir", "ve", "ile", "bu", "da", "de", "mi", "mı", "mu", "mü", "için", "olan", "olarak",
    "sonra", "önce", "gibi", "daha", "çok", "az", "şu", "o", "ise", "ancak", "fakat"
}
_SPACY_MODEL = None
_SPACY_LOAD_ATTEMPTED = False


def _load_spacy():
    """Lazy-load Turkish spaCy model when available."""
    global _SPACY_MODEL, _SPACY_LOAD_ATTEMPTED
    if _SPACY_LOAD_ATTEMPTED:
        return _SPACY_MODEL
    _SPACY_LOAD_ATTEMPTED = True
    try:
        import spacy  # type: ignore
        for name in ("tr_core_news_sm", "tr_core_news_trf"):
            try:
                _SPACY_MODEL = spacy.load(name)
                return _SPACY_MODEL
            except Exception:
                continue
    except Exception:
        return None
    return None


def process(text: str) -> dict:
    """Process Turkish text, preserving Turkish characters."""
    nlp = _load_spacy()
    if not nlp:
        result = generic.process(text)
        result["tokens"] = [t for t in result["tokens"] if t not in CUSTOM_TR_STOPWORDS]
        result["keywords"] = generic.extract_keywords(result["tokens"])
        result["status"] = "partial"
        return result
    doc = nlp(generic.clean_text(text))
    tokens = [t.text.lower() for t in doc if not t.is_punct and not t.is_space and len(t.text) >= 2 and t.text.lower() not in CUSTOM_TR_STOPWORDS]
    lemmas = [t.lemma_ for t in doc if t.text.lower() in tokens]
    return {
        "tokens": tokens,
        "lemmas": lemmas,
        "entities": [{"text": e.text, "label": e.label_} for e in doc.ents],
        "keywords": generic.extract_keywords(tokens),
        "cleaned_text": generic.clean_text(text),
        "status": "success",
    }
