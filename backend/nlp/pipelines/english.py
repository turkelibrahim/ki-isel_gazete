"""English NLP pipeline with optional spaCy and safe fallback."""
from __future__ import annotations

from . import generic

_SPACY_MODEL = None
_SPACY_LOAD_ATTEMPTED = False


def _load_spacy():
    """Lazy-load English spaCy model when available."""
    global _SPACY_MODEL, _SPACY_LOAD_ATTEMPTED
    if _SPACY_LOAD_ATTEMPTED:
        return _SPACY_MODEL
    _SPACY_LOAD_ATTEMPTED = True
    try:
        import spacy  # type: ignore
        _SPACY_MODEL = spacy.load("en_core_web_sm")
    except Exception:
        _SPACY_MODEL = None
    return _SPACY_MODEL


def process(text: str) -> dict:
    """Process English text using spaCy when available."""
    nlp = _load_spacy()
    if not nlp:
        return generic.process(text)
    doc = nlp(generic.clean_text(text))
    tokens = [t.text.lower() for t in doc if not t.is_stop and not t.is_punct and not t.is_space and len(t.text) >= 2]
    return {
        "tokens": tokens,
        "lemmas": [t.lemma_ for t in doc if t.text.lower() in tokens],
        "entities": [{"text": e.text, "label": e.label_} for e in doc.ents],
        "keywords": generic.extract_keywords(tokens),
        "cleaned_text": generic.clean_text(text),
        "status": "success",
    }
