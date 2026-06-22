"""Production news deduplication package for SmartNewspaper."""

from .duplicate_detector import DuplicateDetector, DedupeConfig
from .models import RawNewsArticle, ClusteredNewsArticle, SourceVersion

__all__ = [
    "DuplicateDetector",
    "DedupeConfig",
    "RawNewsArticle",
    "ClusteredNewsArticle",
    "SourceVersion",
]
