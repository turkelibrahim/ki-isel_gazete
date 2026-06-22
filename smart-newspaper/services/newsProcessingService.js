const crypto = require("crypto");

const CONFIDENCE_THRESHOLD = Number(process.env.NLP_CONFIDENCE_THRESHOLD || 0.85);
const MIN_TEXT_LENGTH = Number(process.env.NLP_MIN_TEXT_LENGTH || 20);
const PROCESSING_CACHE_LIMIT = 1000;
const TR_STOPWORDS = new Set([
  "bir", "ve", "ile", "bu", "da", "de", "mi", "mı", "mu", "mü", "için", "olan", "olarak",
  "sonra", "önce", "gibi", "daha", "çok", "az", "şu", "o", "ise", "ancak", "fakat", "veya"
]);
const EN_STOPWORDS = new Set([
  "the", "and", "or", "for", "with", "from", "this", "that", "are", "was", "were", "has", "have", "had", "will", "would", "about", "after", "before", "into", "over", "under"
]);
const PIPELINE_MAP = { tr: "turkish", en: "english", de: "generic", fr: "generic", ar: "generic", es: "generic", ru: "generic" };
const processingCache = new Map();

function stripHtml(value = "") {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ");
}

function normalizeWhitespace(value = "") {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function cleanForLanguageDetection(text = "") {
  return normalizeWhitespace(stripHtml(text)
    .replace(/https?:\/\/\S+/gi, " ")
    .replace(/www\.\S+/gi, " ")
    .replace(/[0-9]+/g, " ")
    .replace(/[\u{1F300}-\u{1FAFF}]/gu, " "));
}

function detectLanguage(text = "") {
  const cleaned = cleanForLanguageDetection(text);
  if (!cleaned || cleaned.length < MIN_TEXT_LENGTH) {
    return { detected_lang: "unknown", confidence: 0, is_reliable: false, fallback_used: false, candidates: [] };
  }

  const sample = cleaned.slice(0, 1200);
  const lower = sample.toLocaleLowerCase("tr-TR");
  const trChars = (sample.match(/[çğıİöşüÇĞÖŞÜ]/g) || []).length;
  const arChars = (sample.match(/[\u0600-\u06FF]/g) || []).length;
  const cyrChars = (sample.match(/[\u0400-\u04FF]/g) || []).length;
  const latinWords = (sample.match(/[A-Za-zÇĞİÖŞÜçğıöşü]{2,}/g) || []).length;
  const enHints = [" the ", " and ", " with ", " from ", " says ", " government ", " president ", " market "].filter((needle) => ` ${lower} `.includes(needle)).length;
  const trHints = [" bir ", " ve ", " için ", " haber ", " türkiye ", " açıklama ", " son dakika ", " ekonomi "].filter((needle) => ` ${lower} `.includes(needle)).length;

  let detected = "unknown";
  let confidence = 0.55;
  if (arChars > 8) {
    detected = "ar"; confidence = 0.94;
  } else if (cyrChars > 8) {
    detected = "ru"; confidence = 0.91;
  } else if (trChars >= 2 || trHints >= 2) {
    detected = "tr"; confidence = Math.min(0.99, 0.82 + trChars * 0.025 + trHints * 0.04);
  } else if (enHints >= 2 || (latinWords >= 8 && trChars === 0)) {
    detected = "en"; confidence = Math.min(0.96, 0.78 + enHints * 0.05);
  }

  const isReliable = confidence >= CONFIDENCE_THRESHOLD && detected !== "unknown";
  return {
    detected_lang: isReliable ? detected : "unknown",
    confidence: Number(confidence.toFixed(3)),
    is_reliable: isReliable,
    fallback_used: !isReliable,
    candidates: [{ lang: detected, prob: Number(confidence.toFixed(3)) }]
  };
}

function selectPipeline(detection) {
  if (!detection || !detection.is_reliable) return "generic";
  return PIPELINE_MAP[detection.detected_lang] || "generic";
}

function tokenize(text = "", language = "generic") {
  const stopwords = language === "turkish" ? TR_STOPWORDS : EN_STOPWORDS;
  return normalizeWhitespace(stripHtml(text).toLocaleLowerCase("tr-TR")
    .replace(/[^\p{L}\p{N}\sçğıöşüÇĞİÖŞÜ]/gu, " "))
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length >= 2 && !stopwords.has(token));
}

function keywordList(tokens = [], limit = 12) {
  const counts = new Map();
  for (const token of tokens) counts.set(token, (counts.get(token) || 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "tr")).slice(0, limit).map(([token]) => token);
}

function extractEntities(text = "") {
  const clean = stripHtml(text);
  const organizations = [...new Set((clean.match(/\b[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9&.\-]{2,}(?:\s+[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9&.\-]{2,}){0,3}/g) || []).slice(0, 12))];
  const locations = [...new Set((clean.match(/\b(Türkiye|Ankara|İstanbul|İzmir|Bursa|Antalya|Paris|London|Berlin|New York|Washington|Moskova|Kahire|Gazze|İran|Irak|Suriye|ABD|Avrupa)\b/gi) || []).slice(0, 12))];
  const dates = [...new Set((clean.match(/\b\d{1,2}\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\b/gi) || []).slice(0, 10))];
  const money = [...new Set((clean.match(/\b(?:\d+[,.]?\d*\s*)?(?:TL|₺|USD|EUR|dolar|euro|sterlin|altın)\b/gi) || []).slice(0, 10))];
  const people = [...new Set((clean.match(/\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\b/g) || []).filter((item) => !locations.some((loc) => item.toLowerCase().includes(loc.toLowerCase()))).slice(0, 12))];
  return [
    ...people.map((text) => ({ text, label: "PERSON" })),
    ...organizations.map((text) => ({ text, label: "ORG" })),
    ...locations.map((text) => ({ text, label: "GPE" })),
    ...dates.map((text) => ({ text, label: "DATE" })),
    ...money.map((text) => ({ text, label: "MONEY" }))
  ];
}

function normalizeTitle(title = "") {
  return normalizeWhitespace(String(title || "")
    .toLocaleLowerCase("tr-TR")
    .replace(/\b(son dakika|breaking|özel haber|canlı|video)\b/giu, " ")
    .replace(/[^\p{L}\p{N}\sçğıöşüÇĞİÖŞÜ]/gu, " "));
}

function canonicalizeUrl(value = "") {
  try {
    const parsed = new URL(String(value || ""));
    ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "source"].forEach((param) => parsed.searchParams.delete(param));
    parsed.hash = "";
    parsed.pathname = parsed.pathname.replace(/\/$/, "").replace(/^\/m\//, "/");
    parsed.protocol = "https:";
    return parsed.toString().toLowerCase();
  } catch {
    return String(value || "").trim().toLowerCase();
  }
}

function dedupeKeyFor(article, detectedLang) {
  const date = article.publishedAt || article.published_at || article.date || article.fetchedAt || "";
  const day = date ? new Date(date).toISOString().slice(0, 10) : "unknown-date";
  return crypto.createHash("sha1").update(`${normalizeTitle(article.title || article.originalTitle || "")}|${detectedLang}|${day}`).digest("hex").slice(0, 24);
}

function formatForNewspaper({ article, title, summary, pipelineName, keywords }) {
  const cleanedTitle = normalizeWhitespace(title).slice(0, 120) || "Başlıksız haber";
  const cleanSummary = normalizeWhitespace(summary || article.description || article.fullText || "").slice(0, 360) || cleanedTitle;
  const importance = Math.min(0.99, 0.35 + Math.min(0.25, (article.sourceCount || 1) * 0.03) + Math.min(0.2, keywords.length * 0.02) + (article.imageUrl ? 0.12 : 0));
  return {
    newspaper_title: cleanedTitle,
    newspaper_summary: cleanSummary,
    newspaper_excerpt: cleanSummary.slice(0, 180),
    reading_lang: "tr",
    page_category: article.category || "Gündem",
    importance_score: Number(importance.toFixed(3)),
    pipeline_name: pipelineName
  };
}

function translationFields(article, lang) {
  const title = article.originalTitle || article.title || "";
  const content = article.originalContent || article.fullText || article.content || article.description || article.summary || "";
  const summary = article.originalSummary || article.summary || article.description || "";
  const titleTr = lang === "tr" ? title : (article.translatedTitle || article.title_tr || "");
  const titleEn = lang === "en" ? title : (article.title_en || article.translations?.en?.title || "");
  const contentTr = lang === "tr" ? content : (article.content_tr || article.translations?.tr?.content || "");
  const contentEn = lang === "en" ? content : (article.content_en || article.translations?.en?.content || "");
  return {
    original_lang: lang,
    title_original: title,
    content_original: content,
    summary_original: summary,
    title_tr: titleTr,
    content_tr: contentTr,
    title_en: titleEn,
    content_en: contentEn,
    translation_status: lang === "tr" || lang === "en" ? "prepared" : "skipped",
    provider: null,
    error_message: null
  };
}

function trimProcessingCache() {
  while (processingCache.size > PROCESSING_CACHE_LIMIT) processingCache.delete(processingCache.keys().next().value);
}

function processArticle(article = {}) {
  const id = String(article.id || article.url || crypto.createHash("sha1").update(JSON.stringify(article)).digest("hex"));
  const sourceText = [article.title, article.summary, article.description, article.fullText, article.content].filter(Boolean).join("\n");
  const cacheFingerprint = crypto.createHash("sha1").update(`${id}|${sourceText.slice(0, 1500)}`).digest("hex");
  if (processingCache.has(cacheFingerprint)) return processingCache.get(cacheFingerprint);

  const started = Date.now();
  try {
    const detection = detectLanguage(sourceText);
    const pipelineName = selectPipeline(detection);
    const tokens = tokenize(sourceText, pipelineName);
    const keywords = keywordList(tokens);
    const entities = extractEntities(sourceText);
    const detectedLang = detection.detected_lang === "unknown" ? "unknown" : detection.detected_lang;
    const translation = translationFields(article, detectedLang === "unknown" ? "tr" : detectedLang);
    const normalizedTitle = normalizeTitle(article.title || article.originalTitle || "");
    const dedupeKey = dedupeKeyFor(article, detectedLang);
    const newspaper = formatForNewspaper({ article, title: article.title || translation.title_original, summary: article.summary || article.description || translation.summary_original, pipelineName, keywords });
    const result = {
      id,
      raw: article,
      detection,
      translation,
      pipeline_name: pipelineName,
      tokens,
      lemmas: pipelineName === "generic" ? [] : tokens,
      entities,
      keywords,
      cleaned_text: normalizeWhitespace(stripHtml(sourceText)).slice(0, 4000),
      normalized_title: normalizedTitle,
      canonical_url: canonicalizeUrl(article.url || article.sourceUrl || article.link || ""),
      dedupe_key: dedupeKey,
      cluster_id: article.clusterId || `cluster_${dedupeKey.slice(0, 14)}`,
      processing_status: sourceText.trim() ? (pipelineName === "generic" ? "partial" : "success") : "partial",
      error_message: null,
      newspaper,
      personalization: {
        topics: [...new Set([article.category, ...(article.topics || []), ...keywords.slice(0, 4)].filter(Boolean))],
        countries: entities.filter((e) => e.label === "GPE").map((e) => e.text),
        cities: entities.filter((e) => e.label === "GPE").map((e) => e.text),
        people: entities.filter((e) => e.label === "PERSON").map((e) => e.text),
        organizations: entities.filter((e) => e.label === "ORG").map((e) => e.text),
        importance_score: newspaper.importance_score,
        freshness_score: 0,
        personalization_tags: keywords.slice(0, 8)
      },
      duration_ms: Date.now() - started
    };
    processingCache.set(cacheFingerprint, result);
    trimProcessingCache();
    return result;
  } catch (error) {
    return {
      id,
      raw: article,
      detection: { detected_lang: "unknown", confidence: 0, is_reliable: false, fallback_used: true, candidates: [] },
      translation: null,
      pipeline_name: "generic",
      tokens: [],
      lemmas: [],
      entities: [],
      keywords: [],
      cleaned_text: normalizeWhitespace(stripHtml(sourceText)),
      normalized_title: normalizeTitle(article.title || ""),
      dedupe_key: dedupeKeyFor(article, "unknown"),
      cluster_id: null,
      processing_status: "failed",
      error_message: error.message || String(error),
      duration_ms: Date.now() - started
    };
  }
}

function enrichFeedArticle(article = {}, options = {}) {
  const processed = processArticle(article);
  const tr = processed.translation || {};
  const entities = processed.entities || [];
  const newspaper = processed.newspaper || {};
  const personalization = processed.personalization || {};
  const sourceName = article.sourceName || article.source || article.publisher || "Bilinmeyen kaynak";
  const sourceUrl = article.sourceUrl || article.url || article.link || "";
  const sourceLogo = article.sourceLogo || article.sourceIcon || article.icon || "";
  const titleTr = tr.title_tr || article.translatedTitle || (processed.detection.detected_lang === "tr" ? article.title : "");
  const titleEn = tr.title_en || (processed.detection.detected_lang === "en" ? article.title : "");
  return {
    ...article,
    cluster_id: article.cluster_id || processed.cluster_id,
    clusterId: article.clusterId || processed.cluster_id,
    title_original: tr.title_original || article.originalTitle || article.title || "",
    content_original: tr.content_original || article.originalContent || article.fullText || article.content || "",
    title_tr: titleTr,
    content_tr: tr.content_tr || article.translatedContent || "",
    title_en: titleEn,
    content_en: tr.content_en || "",
    original_lang: tr.original_lang || article.originalLanguage || processed.detection.detected_lang,
    originalLanguage: article.originalLanguage || tr.original_lang || processed.detection.detected_lang,
    detected_lang: processed.detection.detected_lang,
    language_confidence: processed.detection.confidence,
    language_detection_reliable: processed.detection.is_reliable,
    translation_status: tr.translation_status || "skipped",
    pipeline_name: processed.pipeline_name,
    cleaned_text: processed.cleaned_text,
    normalized_title: processed.normalized_title,
    canonical_url: processed.canonical_url,
    dedupe_key: processed.dedupe_key,
    dedupeKey: article.dedupeKey || processed.dedupe_key,
    source_name: sourceName,
    source_url: sourceUrl,
    source_logo: sourceLogo,
    source_count: article.sourceCount || article.source_count || (Array.isArray(article.sources) ? article.sources.length : 1),
    entities,
    namedEntities: article.namedEntities || {
      people: personalization.people || [],
      organizations: personalization.organizations || [],
      locations: personalization.cities || [],
      countries: personalization.countries || [],
      diseases: [],
      events: [],
      topics: personalization.topics || []
    },
    keywords: processed.keywords,
    topics: personalization.topics || article.topics || article.tags || [],
    countries: personalization.countries || [],
    cities: personalization.cities || [],
    people: personalization.people || [],
    organizations: personalization.organizations || [],
    newspaper_title: newspaper.newspaper_title || article.title || "",
    newspaper_summary: newspaper.newspaper_summary || article.summary || "",
    newspaper_excerpt: newspaper.newspaper_excerpt || article.summary || "",
    reading_lang: options.readingLang || newspaper.reading_lang || "tr",
    page_category: newspaper.page_category || article.category || "Gündem",
    importance_score: newspaper.importance_score || 0,
    processing_status: processed.processing_status,
    processing_error_message: processed.error_message
  };
}

function processBatch(articles = []) {
  return (Array.isArray(articles) ? articles : []).map((article) => processArticle(article));
}

function health() {
  return {
    enabled: String(process.env.NLP_ENABLED || "true") !== "false",
    service: "node-news-processing-service",
    confidenceThreshold: CONFIDENCE_THRESHOLD,
    minTextLength: MIN_TEXT_LENGTH,
    cacheSize: processingCache.size,
    supportedLanguages: ["tr", "en", "de", "fr", "ar", "es", "ru"],
    pipelines: ["turkish", "english", "generic"],
    translationEnabled: String(process.env.TRANSLATION_ENABLED || "false") === "true"
  };
}

module.exports = {
  detectLanguage,
  selectPipeline,
  tokenize,
  normalizeTitle,
  canonicalizeUrl,
  dedupeKeyFor,
  processArticle,
  processBatch,
  enrichFeedArticle,
  health
};
