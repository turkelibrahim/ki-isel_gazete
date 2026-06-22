"""User prompt builder for SmartNewspaper LLM categorization requests."""
from __future__ import annotations

import json

from backend.llm_categorizer.models import LLMCategorizationRequest

MAX_CONTENT_CHARS = 2000


def build_user_prompt(request: LLMCategorizationRequest, retry_count: int = 0, max_content_chars: int = MAX_CONTENT_CHARS) -> str:
    """Build a compact prompt preserving headline, summary and model predictions."""
    content_preview = (request.content or "")[:max_content_chars]
    if request.content and len(request.content) > max_content_chars:
        content_preview += "... [içerik kısaltıldı]"

    prompt = f"""
Haber Başlığı:
{request.title}

Haber Özeti:
{request.summary or ""}

Haber İçeriği:
{content_preview}

Dil:
{request.language}

Kaynak:
{request.source_name or ""}

LLM'e gönderilme nedeni:
{request.trigger_reason}

Mevcut ML tahmini:
{json.dumps(request.ml_prediction, ensure_ascii=False)}

Çoklu etiket tahmini:
{json.dumps(request.multilabel_prediction or {}, ensure_ascii=False)}

Ana kategori tahmini:
{json.dumps(request.category_prediction or {}, ensure_ascii=False)}

Bu haberi analiz et ve yalnızca izinli kategorilerden uygun olanları JSON formatında döndür.
""".strip()

    if retry_count > 0:
        prompt += """

Önemli uyarı:
Önceki yanıt geçersiz kategori veya geçersiz JSON içeriyordu.
Sadece izinli kategori listesindeki değerleri kullan.
Uygun kategori yoksa categories alanını boş liste yap.
""".strip()
    return prompt
