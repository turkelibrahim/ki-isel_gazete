"use strict";

const ALLOWED_LABELS = Object.freeze([
  "Teknoloji",
  "Siyaset",
  "Spor",
  "Ekonomi",
  "Eğlence",
  "Sağlık",
  "Bilim",
  "Dünya",
  "Yaşam"
]);

const FORBIDDEN_LABELS = Object.freeze(["Gündem", "Diğer", "Genel", "Bilinmeyen", "Other", "Unknown"]);
const DEFAULT_LABEL_THRESHOLD = Number(process.env.MULTILABEL_DEFAULT_THRESHOLD || 0.56);
const RELIABLE_LABEL_THRESHOLD = Number(process.env.MULTILABEL_RELIABLE_THRESHOLD || 0.85);
const MIN_CLASSIFIABLE_TEXT_LENGTH = Number(process.env.MULTILABEL_MIN_TEXT_LENGTH || 24);

const LABEL_RULES = Object.freeze({
  "Teknoloji": Object.freeze({
    "teknoloji": 1.8, "yapay zeka": 2.6, "ai": 1.4, "openai": 2.5, "chatgpt": 2.3,
    "gemini": 1.7, "claude": 1.5, "robot": 1.5, "yazılım": 1.9, "siber": 1.9,
    "girişim": 1.4, "startup": 1.7, "uygulama": 1.2, "telefon": 1.2, "nvidia": 2.0,
    "çip": 1.7, "chip": 1.5, "semiconductor": 1.7, "artificial intelligence": 2.6,
    "software": 1.9, "cybersecurity": 2.0, "technology": 1.9, "apple": 1.1, "google": 1.1, "api": 1.2
  }),
  "Siyaset": Object.freeze({
    "siyaset": 1.8, "seçim": 2.1, "parti": 1.5, "meclis": 1.9, "tbmm": 2.2,
    "cumhurbaşkanı": 2.0, "bakan": 1.5, "milletvekili": 1.8, "chp": 2.0, "ak parti": 2.0,
    "mhp": 1.8, "iyi parti": 1.8, "yasa teklifi": 2.2, "anayasa": 1.9, "kabine": 1.6,
    "politics": 1.9, "election": 2.1, "parliament": 2.0, "president": 1.5, "government bill": 2.0,
    "senate": 1.6, "congress": 1.7
  }),
  "Spor": Object.freeze({
    "spor": 1.6, "futbol": 2.2, "basketbol": 2.1, "voleybol": 2.1, "süper lig": 2.3,
    "maç": 1.9, "gol": 1.7, "transfer": 1.7, "galatasaray": 2.1, "fenerbahçe": 2.1,
    "beşiktaş": 2.1, "trabzonspor": 2.0, "uefa": 1.9, "nba": 1.9, "champions league": 2.1,
    "football": 2.1, "basketball": 2.1, "match": 1.7, "goal": 1.6
  }),
  "Ekonomi": Object.freeze({
    "ekonomi": 1.8, "dolar": 2.0, "euro": 1.8, "altın": 1.8, "borsa": 2.0,
    "bist": 2.2, "enflasyon": 2.2, "faiz": 1.9, "merkez bankası": 2.3, "piyasa": 1.5,
    "kredi": 1.4, "vergi": 1.5, "zam": 1.2, "maaş": 1.3, "petrol": 1.3,
    "kripto": 1.7, "finans": 1.8, "yatırım": 1.6, "market": 1.4, "stocks": 2.0,
    "inflation": 2.2, "central bank": 2.3, "economy": 1.9, "rate cut": 1.8, "interest rate": 1.9,
    "investment": 1.5
  }),
  "Eğlence": Object.freeze({
    "eğlence": 1.8, "magazin": 2.0, "ünlü": 1.7, "dizi": 1.8, "yarışma": 1.5,
    "televizyon": 1.5, "oyun": 1.4, "game": 1.4, "celebrity": 2.0, "entertainment": 1.9,
    "series": 1.6, "streaming": 1.5, "netflix": 1.6
  }),
  "Sağlık": Object.freeze({
    "sağlık": 2.0, "hastane": 1.8, "doktor": 1.7, "hasta": 1.5, "ilaç": 1.7,
    "tedavi": 1.9, "ameliyat": 1.8, "aşı": 1.9, "virüs": 1.7, "kanser": 2.1,
    "health": 2.0, "hospital": 1.8, "doctor": 1.7, "vaccine": 1.9, "treatment": 1.9,
    "medicine": 1.6, "cancer": 2.1
  }),
  "Bilim": Object.freeze({
    "bilim": 2.0, "bilim insanları": 1.9, "araştırma": 1.8, "uzay": 2.1, "nasa": 2.3, "iklim": 1.9,
    "keşif": 1.7, "fosil": 1.8, "deney": 1.6, "teleskop": 1.8, "deprem araştırması": 1.8,
    "science": 2.0, "research": 1.8, "space": 2.1, "climate": 1.9, "discovery": 1.7,
    "scientists": 1.7, "experiment": 1.6
  }),
  "Dünya": Object.freeze({
    "dünya": 1.4, "abd": 1.6, "avrupa": 1.4, "rusya": 1.6, "ukrayna": 1.7,
    "iran": 1.5, "israil": 1.6, "gazze": 1.9, "filistin": 1.9, "çin": 1.5,
    "almanya": 1.3, "fransa": 1.3, "nato": 1.7, "bm": 1.7, "birleşmiş milletler": 1.8,
    "united nations": 1.8, "world": 1.6, "global": 1.3, "war": 1.6, "foreign": 1.5,
    "international": 1.7, "europe": 1.3, "russia": 1.5, "china": 1.4
  }),
  "Yaşam": Object.freeze({
    "yaşam": 1.7, "aile": 1.4, "eğitim": 1.6, "okul": 1.4, "öğrenci": 1.4,
    "seyahat": 1.6, "turizm": 1.6, "moda": 1.5, "yemek": 1.6, "tarif": 1.6,
    "ev": 1.2, "life": 1.7, "travel": 1.6, "education": 1.6, "school": 1.4,
    "lifestyle": 1.8, "food": 1.4, "recipe": 1.6
  })
});

const MULTILABEL_CONFIG = Object.freeze({
  allowedLabels: ALLOWED_LABELS,
  forbiddenLabels: FORBIDDEN_LABELS,
  numLabels: ALLOWED_LABELS.length,
  defaultThreshold: DEFAULT_LABEL_THRESHOLD,
  reliableThreshold: RELIABLE_LABEL_THRESHOLD,
  thresholds: Object.freeze(Object.fromEntries(ALLOWED_LABELS.map((label) => [label, Number(process.env[`MULTILABEL_THRESHOLD_${slugifyEnv(label)}`] || DEFAULT_LABEL_THRESHOLD)]))),
  model: Object.freeze({
    architecture: "sigmoid-independent-labels",
    lossCompatibleWith: "BCEWithLogitsLoss",
    softmax: false,
    bertReady: true,
    currentSource: "keyword"
  })
});

function slugifyEnv(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ı/g, "i")
    .replace(/İ/g, "I")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

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

function articleText(article = {}) {
  const main = article.main_article || article.mainArticle || {};
  return [
    article.title, article.summary, article.description, article.fullText, article.content,
    article.displayTitle, article.displaySummary, article.originalTitle, article.originalSummary,
    main.title, main.summary, main.description, main.fullText, main.content
  ].filter(Boolean).join("\n");
}

function keywordHit(normalizedText, normalizedKeyword) {
  if (!normalizedKeyword) return false;
  if (normalizedKeyword.includes(" ")) return normalizedText.includes(normalizedKeyword);
  return (` ${normalizedText} `).includes(` ${normalizedKeyword} `);
}

function sigmoid(logit) {
  if (logit >= 40) return 1;
  if (logit <= -40) return 0;
  return 1 / (1 + Math.exp(-logit));
}

function roundScore(value) {
  return Number(Math.max(0, Math.min(1, Number(value) || 0)).toFixed(4));
}

function validateLabels(labels = []) {
  const rejected = [];
  const incoming = new Set();
  for (const label of Array.isArray(labels) ? labels : []) {
    if (ALLOWED_LABELS.includes(label)) incoming.add(label);
    else {
      rejected.push(label);
      if (label) console.warn(`[multilabel] rejected unsupported label: ${label}`);
    }
  }
  return {
    labels: ALLOWED_LABELS.filter((label) => incoming.has(label)),
    rejectedLabels: rejected
  };
}

function normalizeLabelScores(scores = {}) {
  return Object.fromEntries(ALLOWED_LABELS.map((label) => [label, roundScore(scores[label])]));
}

function validatePrediction(payload = {}) {
  const { labels, rejectedLabels } = validateLabels(payload.labels || []);
  const labelScores = normalizeLabelScores(payload.label_scores || payload.labelScores || {});
  const labelVector = ALLOWED_LABELS.map((label) => (labels.includes(label) ? 1 : 0));
  const noLabelDetected = labels.length === 0;
  return {
    labels,
    label_scores: labelScores,
    labelScores,
    label_vector: labelVector,
    labelVector,
    is_multilabel_reliable: Boolean(labels.length && payload.is_multilabel_reliable),
    isMultilabelReliable: Boolean(labels.length && payload.is_multilabel_reliable),
    no_label_detected: noLabelDetected,
    noLabelDetected,
    num_labels: ALLOWED_LABELS.length,
    numLabels: ALLOWED_LABELS.length,
    label_source: payload.label_source || payload.labelSource || "keyword",
    labelSource: payload.label_source || payload.labelSource || "keyword",
    rejected_labels: [...rejectedLabels, ...(Array.isArray(payload.rejected_labels) ? payload.rejected_labels : [])],
    rejectedLabels: [...rejectedLabels, ...(Array.isArray(payload.rejected_labels) ? payload.rejected_labels : [])],
    fallback_category: payload.fallback_category || payload.fallbackCategory || (noLabelDetected ? "Diğer" : null),
    fallbackCategory: payload.fallback_category || payload.fallbackCategory || (noLabelDetected ? "Diğer" : null)
  };
}

function rawRuleScores(text) {
  const normalized = normalizeText(text);
  const scores = Object.fromEntries(ALLOWED_LABELS.map((label) => [label, 0]));
  const hits = Object.fromEntries(ALLOWED_LABELS.map((label) => [label, []]));
  for (const label of ALLOWED_LABELS) {
    const rules = LABEL_RULES[label] || {};
    for (const [keyword, weight] of Object.entries(rules)) {
      const normalizedKeyword = normalizeText(keyword);
      if (keywordHit(normalized, normalizedKeyword)) {
        scores[label] += Number(weight) || 1;
        hits[label].push(keyword);
      }
    }
  }
  return { scores, hits };
}

function scoreLabels(article = {}) {
  const text = articleText(article);
  const normalized = normalizeText(text);
  if (normalized.length < MIN_CLASSIFIABLE_TEXT_LENGTH) {
    return Object.fromEntries(ALLOWED_LABELS.map((label) => [label, 0]));
  }
  const { scores, hits } = rawRuleScores(text);
  const textLengthBonus = Math.min(0.25, normalized.length / 700);
  const labelScores = {};
  for (const label of ALLOWED_LABELS) {
    const hitBonus = Math.min(0.35, hits[label].length * 0.08);
    const logit = -2.65 + scores[label] * 0.92 + hitBonus + textLengthBonus;
    labelScores[label] = roundScore(sigmoid(logit));
  }
  return labelScores;
}

function classifyArticleLabels(article = {}) {
  try {
    const text = articleText(article);
    const normalized = normalizeText(text);
    if (normalized.length < MIN_CLASSIFIABLE_TEXT_LENGTH) {
      return validatePrediction({
        labels: [],
        label_scores: Object.fromEntries(ALLOWED_LABELS.map((label) => [label, 0])),
        is_multilabel_reliable: false,
        label_source: "fallback",
        fallback_category: article.category || "Diğer"
      });
    }

    const labelScores = scoreLabels(article);
    const { scores: rawScores, hits } = rawRuleScores(text);
    const labels = ALLOWED_LABELS.filter((label) => {
      const threshold = Number(MULTILABEL_CONFIG.thresholds[label] || DEFAULT_LABEL_THRESHOLD);
      if (labelScores[label] < threshold) return false;
      return rawScores[label] >= 1.25 || hits[label].length >= 2 || labelScores[label] >= 0.72;
    });
    const reliable = labels.length > 0 && Math.max(...labels.map((label) => labelScores[label])) >= RELIABLE_LABEL_THRESHOLD;
    return validatePrediction({
      labels,
      label_scores: labelScores,
      is_multilabel_reliable: reliable,
      label_source: "keyword",
      fallback_category: labels.length ? null : article.category || "Diğer"
    });
  } catch (error) {
    return validatePrediction({
      labels: [],
      label_scores: Object.fromEntries(ALLOWED_LABELS.map((label) => [label, 0])),
      is_multilabel_reliable: false,
      label_source: "fallback",
      fallback_category: article.category || "Diğer",
      rejected_labels: [`error:${safeString(error.message || error).slice(0, 80)}`]
    });
  }
}

function applyMultilabelToArticle(article = {}, options = {}) {
  const output = article && typeof article === "object" ? article : {};
  const existingLabels = Array.isArray(output.labels) ? output.labels : [];
  const hasExistingReliable = options.preserveReliable !== false
    && existingLabels.length > 0
    && output.is_multilabel_reliable === true;
  const prediction = hasExistingReliable ? validatePrediction(output) : classifyArticleLabels(output);
  Object.assign(output, prediction);

  if (output.main_article && typeof output.main_article === "object") {
    output.main_article = { ...output.main_article, ...classifyArticleLabels(output.main_article) };
  }
  if (output.mainArticle && typeof output.mainArticle === "object") {
    output.mainArticle = { ...output.mainArticle, ...classifyArticleLabels(output.mainArticle) };
  }
  if (Array.isArray(output.sources)) {
    output.sources = output.sources.map((source) => {
      if (!source || typeof source !== "object") return source;
      const sourceArticle = { ...output, ...source, title: source.title || output.title, summary: source.summary || output.summary };
      return { ...source, ...classifyArticleLabels(sourceArticle) };
    });
  }
  return output;
}

function classifyArticlesLabels(articles = [], options = {}) {
  return (Array.isArray(articles) ? articles : []).map((article) => applyMultilabelToArticle({ ...(article || {}) }, options));
}

function groupArticlesByLabel(articles = []) {
  const groups = Object.fromEntries(ALLOWED_LABELS.map((label) => [label, []]));
  for (const article of classifyArticlesLabels(articles, { preserveReliable: true })) {
    for (const label of article.labels || []) groups[label].push(article);
  }
  return Object.fromEntries(Object.entries(groups).filter(([, items]) => items.length > 0));
}

function sortArticlesForPersonalLabels(articles = [], preferences = {}) {
  const preferredLabels = new Set((Array.isArray(preferences.labels) ? preferences.labels : preferences.interests || [])
    .filter((label) => ALLOWED_LABELS.includes(label)));
  return classifyArticlesLabels(articles, { preserveReliable: true }).sort((left, right) => {
    const leftMatches = (left.labels || []).filter((label) => preferredLabels.has(label)).length;
    const rightMatches = (right.labels || []).filter((label) => preferredLabels.has(label)).length;
    if (rightMatches !== leftMatches) return rightMatches - leftMatches;
    const leftBest = Math.max(0, ...(left.labels || []).map((label) => left.label_scores?.[label] || 0));
    const rightBest = Math.max(0, ...(right.labels || []).map((label) => right.label_scores?.[label] || 0));
    if (Math.abs(rightBest - leftBest) > 0.01) return rightBest - leftBest;
    return new Date(right.publishedAt || right.date || 0) - new Date(left.publishedAt || left.date || 0);
  });
}

function buildMultilabelStats(articles = []) {
  const classified = classifyArticlesLabels(articles, { preserveReliable: true });
  const labelCounts = Object.fromEntries(ALLOWED_LABELS.map((label) => [label, 0]));
  let noLabelCount = 0;
  let reliableCount = 0;
  for (const article of classified) {
    if (!article.labels?.length) noLabelCount += 1;
    if (article.is_multilabel_reliable) reliableCount += 1;
    for (const label of article.labels || []) labelCounts[label] += 1;
  }
  return {
    totalArticles: classified.length,
    labelCounts,
    noLabelCount,
    reliableCount,
    numLabels: ALLOWED_LABELS.length,
    generatedAt: new Date().toISOString()
  };
}

module.exports = {
  ALLOWED_LABELS,
  FORBIDDEN_LABELS,
  MULTILABEL_CONFIG,
  LABEL_RULES,
  normalizeText,
  articleText,
  validateLabels,
  validatePrediction,
  scoreLabels,
  classifyArticleLabels,
  classifyArticlesLabels,
  applyMultilabelToArticle,
  groupArticlesByLabel,
  sortArticlesForPersonalLabels,
  buildMultilabelStats
};
