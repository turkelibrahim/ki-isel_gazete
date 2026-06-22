"use strict";

const crypto = require("crypto");

const RELIABLE_CONFIDENCE_THRESHOLD = Number(process.env.CATEGORY_CONFIDENCE_THRESHOLD || 0.85);
const MIN_CLASSIFIABLE_TEXT_LENGTH = Number(process.env.CATEGORY_MIN_TEXT_LENGTH || 24);

const CATEGORY_CONFIG = Object.freeze({
  categories: [
    "Gündem",
    "Siyaset",
    "Ekonomi",
    "Teknoloji",
    "Spor",
    "Sağlık",
    "Bilim",
    "Dünya",
    "Yaşam",
    "Kültür/Sanat",
    "Eğlence",
    "Diğer"
  ],
  aliases: {
    "Kültür-Sanat": "Kültür/Sanat",
    "Kültür Sanat": "Kültür/Sanat",
    "Kultur Sanat": "Kültür/Sanat",
    "Finans": "Ekonomi",
    "Eğitim": "Yaşam",
    "Politika": "Siyaset",
    "Türkiye": "Gündem",
    "Turkiye": "Gündem",
    "Technology": "Teknoloji",
    "Economy": "Ekonomi",
    "Sports": "Spor",
    "Health": "Sağlık",
    "Science": "Bilim",
    "World": "Dünya",
    "Other": "Diğer"
  },
  keywords: {
    "Spor": {
      "spor": 1.2, "futbol": 2.0, "basketbol": 2.0, "voleybol": 2.0, "süper lig": 2.2,
      "maç": 1.8, "gol": 1.6, "transfer": 1.6, "galatasaray": 2.0, "fenerbahçe": 2.0,
      "beşiktaş": 2.0, "trabzonspor": 2.0, "uefa": 1.8, "nba": 1.8, "champions league": 2.0,
      "football": 2.0, "basketball": 2.0, "match": 1.6, "goal": 1.5
    },
    "Ekonomi": {
      "ekonomi": 1.8, "dolar": 2.0, "euro": 1.8, "altın": 1.8, "borsa": 2.0,
      "bist": 2.2, "enflasyon": 2.2, "faiz": 1.8, "merkez bankası": 2.2, "piyasa": 1.5,
      "kredi": 1.4, "vergi": 1.5, "zam": 1.2, "maaş": 1.3, "petrol": 1.3, "kripto": 1.6,
      "market": 1.4, "stocks": 2.0, "inflation": 2.2, "central bank": 2.2, "economy": 1.8,
      "rate cut": 1.8, "interest rate": 1.8
    },
    "Teknoloji": {
      "teknoloji": 1.8, "yapay zeka": 2.4, "ai": 1.4, "openai": 2.4, "chatgpt": 2.2,
      "gemini": 1.6, "claude": 1.4, "robot": 1.5, "yazılım": 1.8, "siber": 1.8,
      "uygulama": 1.2, "telefon": 1.2, "nvidia": 2.0, "chip": 1.5, "startup": 1.6,
      "artificial intelligence": 2.4, "software": 1.8, "cybersecurity": 2.0, "technology": 1.8,
      "apple": 1.1, "google": 1.1, "semiconductor": 1.5
    },
    "Siyaset": {
      "siyaset": 1.8, "seçim": 2.0, "parti": 1.5, "meclis": 1.8, "tbmm": 2.2,
      "cumhurbaşkanı": 2.0, "bakan": 1.5, "milletvekili": 1.8, "chp": 2.0, "ak parti": 2.0,
      "mhp": 1.8, "iyi parti": 1.8, "yasa teklifi": 2.2, "anayasa": 1.8, "kabine": 1.6,
      "politics": 1.8, "election": 2.0, "parliament": 2.0, "president": 1.4, "government bill": 2.0,
      "senate": 1.5, "congress": 1.6
    },
    "Gündem": {
      "gündem": 1.5, "son dakika": 1.2, "kaza": 1.8, "yangın": 1.6, "polis": 1.5,
      "jandarma": 1.5, "mahkeme": 1.4, "belediye": 1.4, "istanbul": 0.8, "ankara": 0.8,
      "izmir": 0.8, "türkiye": 0.7, "toplum": 1.1, "protesto": 1.4, "güvenlik": 1.2,
      "breaking": 1.0, "accident": 1.8, "court": 1.5, "local": 1.0, "fire": 1.4
    },
    "Sağlık": {
      "sağlık": 2.0, "hastane": 1.8, "doktor": 1.7, "hasta": 1.5, "ilaç": 1.6,
      "tedavi": 1.8, "ameliyat": 1.8, "aşı": 1.8, "virüs": 1.6, "kanser": 2.0,
      "health": 2.0, "hospital": 1.8, "doctor": 1.7, "vaccine": 1.8, "treatment": 1.8,
      "medicine": 1.5
    },
    "Bilim": {
      "bilim": 2.0, "araştırma": 1.8, "uzay": 2.0, "nasa": 2.2, "iklim": 1.8,
      "keşif": 1.6, "fosil": 1.7, "deney": 1.5, "deprem araştırması": 1.8,
      "science": 2.0, "research": 1.8, "space": 2.0, "climate": 1.8, "discovery": 1.6,
      "scientists": 1.6
    },
    "Dünya": {
      "dünya": 1.4, "abd": 1.5, "avrupa": 1.3, "rusya": 1.5, "ukrayna": 1.6,
      "iran": 1.4, "israil": 1.5, "gazze": 1.8, "filistin": 1.8, "çin": 1.4,
      "almanya": 1.2, "fransa": 1.2, "nato": 1.6, "bm": 1.6, "united nations": 1.8,
      "world": 1.5, "global": 1.2, "war": 1.5, "foreign": 1.4, "international": 1.6,
      "europe": 1.2, "russia": 1.4, "china": 1.3
    },
    "Yaşam": {
      "yaşam": 1.7, "aile": 1.4, "eğitim": 1.6, "okul": 1.4, "öğrenci": 1.4,
      "seyahat": 1.5, "turizm": 1.5, "moda": 1.4, "yemek": 1.5, "tarif": 1.5,
      "life": 1.6, "travel": 1.5, "education": 1.5, "school": 1.4, "lifestyle": 1.7,
      "food": 1.3
    },
    "Kültür/Sanat": {
      "kültür": 1.8, "sanat": 1.8, "sinema": 1.8, "film": 1.5, "tiyatro": 2.0,
      "kitap": 1.8, "sergi": 1.8, "müze": 1.6, "konser": 1.4, "festival": 1.4,
      "culture": 1.8, "art": 1.8, "cinema": 1.8, "theatre": 1.8, "book": 1.6,
      "museum": 1.6
    },
    "Eğlence": {
      "eğlence": 1.8, "magazin": 2.0, "ünlü": 1.6, "dizi": 1.7, "yarışma": 1.5,
      "televizyon": 1.5, "oyun": 1.4, "game": 1.4, "celebrity": 2.0, "entertainment": 1.8,
      "series": 1.5, "streaming": 1.4
    },
    "Diğer": {}
  },
  sectionOrder: ["Gündem", "Siyaset", "Ekonomi", "Spor", "Teknoloji", "Dünya", "Sağlık", "Bilim", "Yaşam", "Kültür/Sanat", "Eğlence", "Diğer"]
});

const TR_HINTS = new Set(["ve", "bir", "için", "türkiye", "açıklama", "son", "dakika", "bakan", "dolar"]);
const EN_HINTS = new Set(["the", "and", "for", "with", "from", "government", "market", "president", "company"]);
const STOPWORDS = new Set([
  "ve", "ile", "bir", "bu", "şu", "o", "da", "de", "ki", "için", "olan", "olarak", "gibi", "son", "yeni", "haber",
  "the", "and", "or", "for", "with", "from", "this", "that", "are", "was", "were", "has", "have", "had", "will", "would", "about", "news"
]);

function safeString(value) {
  return value == null ? "" : String(value);
}

function stripHtml(value) {
  return safeString(value)
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ");
}

function normalizeText(value) {
  return stripHtml(value)
    .normalize("NFC")
    .replace(/I/g, "ı")
    .replace(/İ/g, "i")
    .toLocaleLowerCase("tr-TR")
    .replace(/https?:\/\/\S+|www\.\S+/gi, " ")
    .replace(/[^0-9a-zçğıöşüâîû\s]+/giu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenize(value, removeStopwords = true) {
  const tokens = normalizeText(value).split(/\s+/).filter(Boolean);
  return removeStopwords ? tokens.filter((token) => token.length >= 2 && !STOPWORDS.has(token)) : tokens;
}

function normalizeCategory(value) {
  const raw = safeString(value).trim();
  if (!raw) return "Diğer";
  if (CATEGORY_CONFIG.categories.includes(raw)) return raw;
  const alias = CATEGORY_CONFIG.aliases[raw] || CATEGORY_CONFIG.aliases[raw.replace(/\//g, "-")];
  return CATEGORY_CONFIG.categories.includes(alias) ? alias : "Diğer";
}

function articleText(article = {}) {
  const main = article.main_article || article.mainArticle || {};
  return [
    article.title, article.summary, article.description, article.fullText, article.content,
    article.displayTitle, article.displaySummary, article.originalTitle, article.originalSummary,
    main.title, main.summary, main.description, main.fullText, main.content,
    article.sourceName, article.source, article.sourceUrl, article.url
  ].filter(Boolean).join("\n");
}

function detectLanguage(text, fallback = "unknown") {
  const normalized = normalizeText(text);
  if (!normalized) return fallback;
  const tokens = normalized.split(/\s+/).filter(Boolean);
  const trChars = (safeString(text).match(/[çğıİöşüÇĞÖŞÜ]/g) || []).length;
  const trScore = trChars * 2 + tokens.filter((token) => TR_HINTS.has(token)).length;
  const enScore = tokens.filter((token) => EN_HINTS.has(token)).length;
  if (trScore >= 2) return "tr";
  if (enScore >= 2 || (tokens.length >= 8 && trChars === 0)) return "en";
  return fallback || "unknown";
}

function keywordHit(normalizedText, normalizedKeyword) {
  if (!normalizedKeyword) return false;
  if (normalizedKeyword.includes(" ")) return normalizedText.includes(normalizedKeyword);
  return (` ${normalizedText} `).includes(` ${normalizedKeyword} `);
}

function scoreKeywordRules(text) {
  const normalized = normalizeText(text);
  const scores = {};
  const hitsByCategory = {};
  for (const [category, keywords] of Object.entries(CATEGORY_CONFIG.keywords)) {
    if (category === "Diğer") continue;
    let score = 0;
    const hits = [];
    for (const [keyword, weight] of Object.entries(keywords)) {
      const normalizedKeyword = normalizeText(keyword);
      if (keywordHit(normalized, normalizedKeyword)) {
        score += Number(weight) || 1;
        hits.push(keyword);
      }
    }
    scores[category] = score;
    hitsByCategory[category] = hits;
  }
  const ordered = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  const [bestCategory = "Diğer", bestScore = 0] = ordered[0] || [];
  const secondScore = ordered[1]?.[1] || 0;
  if (!bestScore) return { category: "Diğer", confidence: 0, scores, hits: [] };
  const margin = Math.max(0, bestScore - secondScore);
  const hitCount = hitsByCategory[bestCategory]?.length || 0;
  let confidence = 0.45 + Math.min(0.30, bestScore / 12) + Math.min(0.20, margin / 7) + Math.min(0.08, hitCount * 0.015);
  if (bestCategory === "Siyaset" && bestScore < 2.8) confidence = Math.min(confidence, 0.74);
  if (bestCategory === "Gündem" && secondScore >= bestScore * 0.85) confidence = Math.min(confidence, 0.78);
  confidence = Math.max(0, Math.min(0.98, confidence));
  return { category: bestCategory, confidence, scores, hits: hitsByCategory[bestCategory] || [] };
}

function buildCategoryProfile(category) {
  const keywords = CATEGORY_CONFIG.keywords[category] || {};
  const tokens = [];
  for (const [keyword, weight] of Object.entries(keywords)) {
    const repeat = Math.max(1, Math.min(5, Math.round(Number(weight || 1) * 2)));
    for (let i = 0; i < repeat; i += 1) tokens.push(...tokenize(keyword, false));
  }
  return tokens;
}

const CATEGORY_PROFILES = Object.fromEntries(
  CATEGORY_CONFIG.categories
    .filter((category) => category !== "Diğer")
    .map((category) => [category, buildCategoryProfile(category)])
);

function vectorize(tokens) {
  const vector = new Map();
  for (const token of tokens) vector.set(token, (vector.get(token) || 0) + 1);
  return vector;
}

const PROFILE_VECTORS = Object.fromEntries(Object.entries(CATEGORY_PROFILES).map(([category, tokens]) => [category, vectorize(tokens)]));

function cosine(left, right) {
  if (!left.size || !right.size) return 0;
  let dot = 0;
  for (const [token, value] of left.entries()) dot += value * (right.get(token) || 0);
  const leftNorm = Math.sqrt([...left.values()].reduce((sum, value) => sum + value * value, 0)) || 1;
  const rightNorm = Math.sqrt([...right.values()].reduce((sum, value) => sum + value * value, 0)) || 1;
  return dot / (leftNorm * rightNorm);
}

function mlFallback(text) {
  const vector = vectorize(tokenize(text));
  const scores = {};
  for (const [category, profile] of Object.entries(PROFILE_VECTORS)) scores[category] = cosine(vector, profile);
  const ordered = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  const [category = "Diğer", bestScore = 0] = ordered[0] || [];
  const secondScore = ordered[1]?.[1] || 0;
  if (bestScore <= 0.025) return { category: "Diğer", confidence: 0, scores };
  const confidence = Math.max(0, Math.min(0.91, 0.35 + bestScore * 0.65 + Math.max(0, bestScore - secondScore) * 0.30));
  return { category, confidence, scores };
}

function classifyArticle(article = {}, options = {}) {
  try {
    const text = articleText(article);
    const normalized = normalizeText(text);
    const detectedLang = detectLanguage(text, article.detected_lang || article.originalLanguage || article.language || "unknown");
    if (normalized.length < MIN_CLASSIFIABLE_TEXT_LENGTH) {
      return {
        category: "Diğer",
        category_confidence: normalized.length ? 0.18 : 0,
        category_source: "fallback",
        is_category_reliable: false,
        detected_lang: detectedLang,
        category_scores: {}
      };
    }

    const rule = scoreKeywordRules(text);
    if (rule.confidence >= RELIABLE_CONFIDENCE_THRESHOLD) {
      return {
        category: normalizeCategory(rule.category),
        category_confidence: Number(rule.confidence.toFixed(4)),
        category_source: "keyword",
        is_category_reliable: true,
        detected_lang: detectedLang,
        category_scores: rule.scores
      };
    }

    const ml = mlFallback(text);
    const useMl = ml.confidence >= rule.confidence;
    let category = normalizeCategory(useMl ? ml.category : rule.category);
    let confidence = useMl ? ml.confidence : rule.confidence;
    let source = useMl ? "ml" : "keyword";

    if (confidence < 0.55) {
      category = "Diğer";
      source = "fallback";
    }

    confidence = Math.max(0, Math.min(0.98, confidence));
    return {
      category,
      category_confidence: Number(confidence.toFixed(4)),
      category_source: source,
      is_category_reliable: confidence >= RELIABLE_CONFIDENCE_THRESHOLD,
      detected_lang: detectedLang,
      category_scores: { ...rule.scores, ...Object.fromEntries(Object.entries(ml.scores || {}).map(([key, value]) => [`ml_${key}`, value])) }
    };
  } catch (error) {
    if (options.throwOnError) throw error;
    return {
      category: "Diğer",
      category_confidence: 0,
      category_source: "fallback",
      is_category_reliable: false,
      detected_lang: "unknown",
      category_scores: {},
      category_error: safeString(error.message || error).slice(0, 160)
    };
  }
}

function applyCategoryToArticle(article = {}, options = {}) {
  const output = article && typeof article === "object" ? article : {};
  const existingConfidence = Number(output.category_confidence ?? output.categoryConfidence ?? 0);
  const existingCategory = normalizeCategory(output.category);
  const hasReliableExisting = options.preserveReliable !== false
    && existingCategory !== "Diğer"
    && existingConfidence >= RELIABLE_CONFIDENCE_THRESHOLD;
  const prediction = hasReliableExisting
    ? {
        category: existingCategory,
        category_confidence: existingConfidence,
        category_source: output.category_source || output.categorySource || "existing",
        is_category_reliable: true,
        detected_lang: output.detected_lang || output.detectedLang || detectLanguage(articleText(output))
      }
    : classifyArticle(output);

  output.category = prediction.category;
  output.category_confidence = Number(prediction.category_confidence || 0);
  output.categoryConfidence = output.category_confidence;
  output.category_source = prediction.category_source;
  output.categorySource = prediction.category_source;
  output.is_category_reliable = Boolean(prediction.is_category_reliable);
  output.isCategoryReliable = output.is_category_reliable;
  output.detected_lang = output.detected_lang || prediction.detected_lang;
  output.detectedLang = output.detected_lang;

  if (output.main_article && typeof output.main_article === "object") {
    const mainPrediction = classifyArticle(output.main_article);
    output.main_article = { ...output.main_article, ...mainPrediction };
  }
  if (output.mainArticle && typeof output.mainArticle === "object") {
    const mainPrediction = classifyArticle(output.mainArticle);
    output.mainArticle = { ...output.mainArticle, ...mainPrediction };
  }

  if (Array.isArray(output.sources)) {
    output.sources = output.sources.map((source) => {
      if (!source || typeof source !== "object") return source;
      const sourceArticle = { ...output, ...source, title: source.title || output.title, summary: source.summary || output.summary };
      const sourcePrediction = classifyArticle(sourceArticle);
      return {
        ...source,
        category: sourcePrediction.category,
        category_confidence: sourcePrediction.category_confidence,
        categoryConfidence: sourcePrediction.category_confidence,
        category_source: sourcePrediction.category_source,
        categorySource: sourcePrediction.category_source,
        is_category_reliable: sourcePrediction.is_category_reliable,
        isCategoryReliable: sourcePrediction.is_category_reliable,
        detected_lang: source.detected_lang || sourcePrediction.detected_lang,
        detectedLang: source.detected_lang || sourcePrediction.detected_lang
      };
    });
  }

  return output;
}

function classifyArticles(articles = [], options = {}) {
  return (Array.isArray(articles) ? articles : []).map((article) => applyCategoryToArticle({ ...(article || {}) }, options));
}

function groupArticlesByCategory(articles = []) {
  const groups = Object.fromEntries(CATEGORY_CONFIG.categories.map((category) => [category, []]));
  for (const article of classifyArticles(articles)) {
    groups[article.category || "Diğer"].push(article);
  }
  return Object.fromEntries(Object.entries(groups).filter(([, items]) => items.length > 0));
}

function sortArticlesForPersonalNewspaper(articles = [], preferences = {}) {
  const preferred = new Set(
    (Array.isArray(preferences.interests) ? preferences.interests : [])
      .map(normalizeCategory)
      .filter((category) => category !== "Diğer")
  );
  const sectionRank = new Map(CATEGORY_CONFIG.sectionOrder.map((category, index) => [category, index]));
  return classifyArticles(articles).sort((left, right) => {
    const prefDiff = Number(preferred.has(right.category)) - Number(preferred.has(left.category));
    if (prefDiff) return prefDiff;
    const sectionDiff = (sectionRank.get(left.category) ?? 99) - (sectionRank.get(right.category) ?? 99);
    if (sectionDiff) return sectionDiff;
    const confidenceDiff = (right.category_confidence || 0) - (left.category_confidence || 0);
    if (Math.abs(confidenceDiff) > 0.01) return confidenceDiff;
    return new Date(right.publishedAt || right.date || 0) - new Date(left.publishedAt || left.date || 0);
  });
}

function buildCategoryStats(articles = []) {
  const groups = groupArticlesByCategory(articles);
  return {
    totalArticles: Array.isArray(articles) ? articles.length : 0,
    categoryCounts: Object.fromEntries(Object.entries(groups).map(([category, items]) => [category, items.length])),
    reliableCount: Object.values(groups).flat().filter((article) => article.is_category_reliable).length,
    generatedAt: new Date().toISOString()
  };
}

function categoryId(category) {
  return crypto.createHash("sha1").update(normalizeCategory(category), "utf8").digest("hex").slice(0, 8);
}

module.exports = {
  CATEGORY_CONFIG,
  RELIABLE_CONFIDENCE_THRESHOLD,
  MIN_CLASSIFIABLE_TEXT_LENGTH,
  normalizeText,
  normalizeCategory,
  detectLanguage,
  classifyArticle,
  classifyArticles,
  applyCategoryToArticle,
  groupArticlesByCategory,
  sortArticlesForPersonalNewspaper,
  buildCategoryStats,
  categoryId
};
