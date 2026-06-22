"use strict";

const crypto = require("crypto");

const TURKISH_STOP_WORDS = new Set([
  "ve", "veya", "ile", "bir", "bu", "şu", "su", "o", "da", "de", "için", "icin", "gibi", "olan", "olarak", "daha", "çok", "cok", "az", "en", "mi", "mı", "mu", "mü",
  "the", "and", "or", "of", "to", "in", "on", "for", "a", "an", "is", "are"
]);

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.filter(Boolean);
    } catch {}
    return value.split(/[;,|]/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

function normalizeTurkishText(text = "") {
  return String(text || "")
    .toLocaleLowerCase("tr-TR")
    .normalize("NFKC")
    .replace(/<[^>]*>/g, " ")
    .replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeTurkishAscii(text = "") {
  return normalizeTurkishText(text)
    .replace(/ç/g, "c")
    .replace(/ğ/g, "g")
    .replace(/ı/g, "i")
    .replace(/ö/g, "o")
    .replace(/ş/g, "s")
    .replace(/ü/g, "u");
}

function simpleStem(token = "") {
  let value = normalizeTurkishAscii(token);
  const suffixes = [
    "lerinden", "larindan", "lerinden", "lerin", "ların", "lari", "leri", "larda", "lerde",
    "inden", "dan", "den", "dir", "dır", "dur", "dür", "lar", "ler", "nin", "nın", "nun", "nün", "in", "un", "ın", "ün", "de", "da", "e", "a"
  ].map(normalizeTurkishAscii);
  for (const suffix of suffixes) {
    if (value.length > suffix.length + 3 && value.endsWith(suffix)) return value.slice(0, -suffix.length);
  }
  return value;
}

function tokenize(text = "") {
  const normal = normalizeTurkishText(text);
  const ascii = normalizeTurkishAscii(text);
  const tokens = `${normal} ${ascii}`
    .split(/\s+/)
    .map(simpleStem)
    .filter((token) => token.length >= 2 && !TURKISH_STOP_WORDS.has(token));
  return [...new Set(tokens)];
}

function getArticleId(article = {}) {
  return String(firstDefined(article.id, article.article_id, article.articleId, article.guid, article.url, "")).trim();
}

function getArticleTitle(article = {}) {
  return firstDefined(article.title, article.headline, article.displayTitle, article.originalTitle, "");
}

function getArticleSummary(article = {}) {
  return firstDefined(article.summary, article.description, article.displaySummary, article.originalSummary, article.aiSummary, "");
}

function getArticleContent(article = {}) {
  return firstDefined(article.content, article.body, article.fullText, article.displayContent, article.originalContent, article.text, "");
}

function getArticleSourceName(article = {}) {
  return firstDefined(article.source_name, article.sourceName, article.source, article.publisher, article.newspaper, article.rss_source, "");
}

function getArticlePublishedAt(article = {}) {
  return firstDefined(article.published_at, article.publishedAt, article.pubDate, article.created_at, article.createdAt, article.fetched_at, article.fetchedAt, article.date, "");
}

function getArticleLabels(article = {}) {
  return [
    ...asArray(article.labels),
    ...asArray(article.tags),
    ...asArray(article.topics),
    article.category,
    article.subcategory
  ].filter(Boolean).map(String);
}

function getArticleSources(article = {}) {
  return asArray(article.sources)
    .filter((item) => item && typeof item === "object")
    .map((item) => firstDefined(item.source_name, item.sourceName, item.source, item.publisher, item.newspaper, item.rss_source, ""))
    .filter(Boolean);
}

function prepareArticleText(article = {}) {
  const title = getArticleTitle(article);
  const summary = getArticleSummary(article);
  const content = getArticleContent(article);
  const labels = getArticleLabels(article).join(" ");
  const source = [getArticleSourceName(article), ...getArticleSources(article)].join(" ");
  const weighted = [
    title, title, title,
    labels, labels, labels,
    article.category || "", article.category || "",
    summary, summary,
    content,
    source
  ].join(" ");
  const clean = normalizeTurkishText(weighted);
  return clean || normalizeTurkishText(`${title} ${article.category || ""}`);
}

function textHash(text = "") {
  return crypto.createHash("sha256").update(String(text || "")).digest("hex");
}

function termFrequency(tokens = []) {
  const tf = new Map();
  for (const token of tokens) tf.set(token, (tf.get(token) || 0) + 1);
  const total = Math.max(1, tokens.length);
  const result = {};
  for (const [token, count] of tf.entries()) result[token] = count / total;
  return result;
}

function buildTfidfModel(articles = []) {
  const docs = [];
  const df = new Map();
  for (const article of articles) {
    const id = getArticleId(article);
    if (!id) continue;
    const text = prepareArticleText(article);
    const tokens = tokenize(text);
    const unique = new Set(tokens);
    for (const token of unique) df.set(token, (df.get(token) || 0) + 1);
    docs.push({ id, article, text, text_hash: textHash(text), tokens, tf: termFrequency(tokens) });
  }
  const n = Math.max(1, docs.length);
  const vectors = new Map();
  for (const doc of docs) {
    const vector = {};
    for (const [token, tfValue] of Object.entries(doc.tf)) {
      const idf = Math.log((1 + n) / (1 + (df.get(token) || 0))) + 1;
      const value = tfValue * idf;
      if (Number.isFinite(value) && value > 0) vector[token] = value;
    }
    vectors.set(doc.id, vector);
  }
  return { vectors, docs, vocabularySize: df.size, builtAt: new Date().toISOString() };
}

function vectorNorm(vector = {}) {
  let sum = 0;
  for (const value of Object.values(vector)) sum += Number(value || 0) ** 2;
  return Math.sqrt(sum);
}

function cosineSimilarity(a = {}, b = {}) {
  const normA = vectorNorm(a);
  const normB = vectorNorm(b);
  if (!normA || !normB) return 0;
  let dot = 0;
  const small = Object.keys(a).length <= Object.keys(b).length ? a : b;
  const large = small === a ? b : a;
  for (const [token, value] of Object.entries(small)) {
    if (large[token]) dot += Number(value || 0) * Number(large[token] || 0);
  }
  return Math.max(0, Math.min(1, dot / (normA * normB)));
}

function addWeightedVector(target = {}, vector = {}, weight = 1) {
  const w = Number(weight || 0);
  if (!w) return target;
  for (const [token, value] of Object.entries(vector || {})) {
    target[token] = (target[token] || 0) + Number(value || 0) * w;
  }
  return target;
}

function divideVector(vector = {}, divisor = 1) {
  const d = Math.max(1e-9, Number(divisor || 0));
  const result = {};
  for (const [token, value] of Object.entries(vector || {})) result[token] = Number(value || 0) / d;
  return result;
}

module.exports = {
  TURKISH_STOP_WORDS,
  asArray,
  firstDefined,
  normalizeTurkishText,
  normalizeTurkishAscii,
  tokenize,
  simpleStem,
  getArticleId,
  getArticleTitle,
  getArticleSummary,
  getArticleContent,
  getArticleSourceName,
  getArticlePublishedAt,
  getArticleLabels,
  getArticleSources,
  prepareArticleText,
  textHash,
  buildTfidfModel,
  cosineSimilarity,
  addWeightedVector,
  divideVector
};
