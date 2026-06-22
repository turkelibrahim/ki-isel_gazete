"""System prompt builder for constrained news categorization."""
from __future__ import annotations

import json

from backend.llm_categorizer.models import ALLOWED_CATEGORY_NAMES
from backend.llm_categorizer.prompts.few_shot import FEW_SHOT_EXAMPLES


def build_system_prompt(include_examples: bool = True) -> str:
    """Build the system prompt with strict output and category constraints."""
    categories = "\n".join(f"- {category}" for category in ALLOWED_CATEGORY_NAMES)
    prompt = f"""
Sen bir haber kategorizasyon uzmanısın.

Sana verilen haber metnini analiz ederek yalnızca izinli kategori listesinden uygun kategorileri seç.

İzinli kategoriler:
{categories}

Kurallar:
1. Sadece yukarıdaki kategorilerden seçim yap.
2. Liste dışı kategori üretme.
3. Bir haber birden fazla kategoriyle ilişkili olabilir.
4. İlgili tüm kategorileri seç.
5. Hiçbir kategori uymuyorsa categories alanını boş liste olarak döndür.
6. Her seçilen kategori için 0.0-1.0 arası güven skoru ver.
7. Yanıtını sadece JSON formatında ver.
8. Markdown, açıklama metni veya ek yorum yazma.

JSON formatı:
{{
  "categories": ["Kategori1", "Kategori2"],
  "confidences": {{
    "Kategori1": 0.95,
    "Kategori2": 0.78
  }},
  "reasoning": "Kısa gerekçe, en fazla 100 kelime"
}}
""".strip()
    if include_examples:
        prompt += "\n\nFew-shot örnekler:\n" + json.dumps(FEW_SHOT_EXAMPLES, ensure_ascii=False, indent=2)
    return prompt
