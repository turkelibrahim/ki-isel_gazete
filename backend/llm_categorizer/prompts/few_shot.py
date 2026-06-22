"""Few-shot examples used by the LLM categorizer prompt."""
from __future__ import annotations

FEW_SHOT_EXAMPLES = [
    {
        "title": "Yapay zeka çipi üretiminde rekor kırıldı",
        "content": "Yeni nesil GPU ve yapay zeka hızlandırıcıları tanıtıldı.",
        "output": {
            "categories": ["Teknoloji"],
            "confidences": {"Teknoloji": 0.97},
            "reasoning": "Haber yapay zeka donanımı ve çip teknolojileri hakkındadır.",
        },
    },
    {
        "title": "Merkez Bankası faiz kararı açıklandı",
        "content": "Para politikası kurulu yeni faiz oranını duyurdu.",
        "output": {
            "categories": ["Ekonomi", "Siyaset"],
            "confidences": {"Ekonomi": 0.91, "Siyaset": 0.72},
            "reasoning": "Faiz kararı ekonomik etkiye sahiptir ve kamu politikasıyla ilişkilidir.",
        },
    },
    {
        "title": "Yerel etkinlik duyurusu",
        "content": "Mahallede küçük bir buluşma düzenlenecek.",
        "output": {
            "categories": [],
            "confidences": {},
            "reasoning": "Haber izinli kategorilerle net biçimde eşleşmemektedir.",
        },
    },
    {
        "title": "Sağlık Bakanlığı yapay zeka destekli teşhis sistemi tanıttı",
        "content": "Hastanelerde kullanılacak görüntü analizi sistemi duyuruldu.",
        "output": {
            "categories": ["Sağlık", "Teknoloji"],
            "confidences": {"Sağlık": 0.94, "Teknoloji": 0.87},
            "reasoning": "Haber sağlık hizmetlerinde yapay zeka kullanımını anlatmaktadır.",
        },
    },
]
