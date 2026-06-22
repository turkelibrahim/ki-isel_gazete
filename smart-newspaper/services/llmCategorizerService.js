"use strict";

const crypto = require("crypto");

const ALLOWED_CATEGORIES = Object.freeze([
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
const ALLOWED_SET = new Set(ALLOWED_CATEGORIES);
const TRIGGER_REASONS = new Set(["low_confidence", "no_label", "model_conflict", "manual", "cluster_conflict"]);
const CATEGORY_CONFIDENCE_THRESHOLD = Number(process.env.LLM_CATEGORY_CONFIDENCE_THRESHOLD || process.env.CATEGORY_CONFIDENCE_THRESHOLD || 0.85);
const MAX_RETRIES = Math.max(0, Math.min(3, Number(process.env.LLM_MAX_RETRIES || 2) || 2));
const CACHE_TTL_MS = Math.max(1000, Number(process.env.LLM_CACHE_TTL_SECONDS || 86400) * 1000);
const CACHE_MAX_SIZE = Math.max(10, Number(process.env.LLM_CACHE_MAX_SIZE || 1000) || 1000);
const MAX_CONTENT_CHARS = Math.max(200, Number(process.env.LLM_MAX_CONTENT_CHARS || 2000) || 2000);
const MAX_PROMPT_TOKENS = Math.max(800, Number(process.env.LLM_MAX_PROMPT_TOKENS || 3000) || 3000);
const DAILY_COST_LIMIT_USD = Math.max(0, Number(process.env.LLM_DAILY_COST_LIMIT_USD || 5.0) || 5.0);
const TIMEOUT_MS = Math.max(1000, Number(process.env.LLM_TIMEOUT_SECONDS || 10) * 1000);

const PRICING = Object.freeze({
  claude: { input: 0.000003, output: 0.000015 },
  gpt4: { input: 0.00000015, output: 0.0000006 },
  fallback: { input: 0, output: 0 }
});

const PROVIDER_MODELS = Object.freeze({
  claude: "claude-3-5-sonnet-20241022",
  gpt4: "gpt-4o-mini",
  fallback: "rule-based-keyword-fallback"
});

const KEYWORD_RULES = Object.freeze({
  Teknoloji: ["yapay zeka", "yazılım", "uygulama", "internet", "dijital", "teknoloji", "robot", "algoritma", "siber", "veri", "gpu", "çip", "api", "openai", "chatgpt", "artificial intelligence", "software", "cybersecurity", "chip", "startup", "nvidia"],
  Siyaset: ["meclis", "hükümet", "seçim", "parti", "cumhurbaşkanı", "bakan", "kanun", "muhalefet", "koalisyon", "parlamento", "politics", "election", "minister", "government", "parliament", "president", "senate", "congress"],
  Spor: ["maç", "gol", "şampiyon", "turnuva", "futbol", "basketbol", "transfer", "stadyum", "antrenman", "lig", "football", "basketball", "match", "goal", "league", "nba", "uefa"],
  Ekonomi: ["faiz", "enflasyon", "dolar", "borsa", "bütçe", "ihracat", "yatırım", "banka", "piyasa", "gelir", "merkez bankası", "ekonomi", "market", "stocks", "inflation", "central bank", "interest rate", "investment", "finance"],
  Eğlence: ["film", "müzik", "konser", "dizi", "sanatçı", "oyuncu", "ödül", "festival", "sinema", "albüm", "celebrity", "entertainment", "series", "streaming", "actor", "music"],
  Sağlık: ["hastalık", "tedavi", "hastane", "ilaç", "doktor", "sağlık", "aşı", "pandemi", "ameliyat", "klinik", "health", "hospital", "doctor", "vaccine", "treatment", "medicine", "cancer"],
  Bilim: ["araştırma", "keşif", "uzay", "deney", "bilim", "nasa", "evren", "kimya", "fizik", "biyoloji", "science", "research", "space", "discovery", "scientists", "climate", "experiment"],
  Dünya: ["uluslararası", "küresel", "nato", "ab", "savaş", "ülke", "dışişleri", "göç", "birleşmiş milletler", "yabancı", "world", "global", "war", "foreign", "international", "united nations", "europe", "russia", "china", "gaza", "israel", "ukraine"],
  Yaşam: ["yemek", "seyahat", "aile", "eğitim", "kültür", "moda", "sağlıklı yaşam", "ilişki", "hobi", "tatil", "life", "travel", "education", "school", "lifestyle", "food", "family"]
});

const responseCache = new Map();
const adminQueue = [];
const usageStatsByDate = new Map();

function safeString(value) {
  return value == null ? "" : String(value);
}

function normalizeText(value) {
  return safeString(value)
    .normalize("NFC")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
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

function estimateTokens(text = "") {
  return Math.max(1, Math.ceil(safeString(text).length / 4));
}

function calculateCost(provider, promptTokens, completionTokens) {
  const pricing = PRICING[provider] || PRICING.gpt4;
  return Number((promptTokens * pricing.input + completionTokens * pricing.output).toFixed(6));
}

function cacheKeyForArticle(article = {}) {
  const seed = `${article.title || ""}|${articleText(article).slice(0, 500)}|${article.detected_lang || article.detectedLang || article.language || "unknown"}`;
  return crypto.createHash("sha256").update(seed, "utf8").digest("hex");
}

function getCached(key) {
  const hit = responseCache.get(key);
  if (!hit) return null;
  if (hit.expiresAt <= Date.now()) {
    responseCache.delete(key);
    return null;
  }
  responseCache.delete(key);
  responseCache.set(key, hit);
  return { ...hit.value, cache_hit: true, cacheHit: true };
}

function setCached(key, value) {
  responseCache.set(key, { value, expiresAt: Date.now() + CACHE_TTL_MS });
  while (responseCache.size > CACHE_MAX_SIZE) {
    responseCache.delete(responseCache.keys().next().value);
  }
}

function getDateKey(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function getUsageStats(date = new Date()) {
  const key = getDateKey(date);
  if (!usageStatsByDate.has(key)) {
    usageStatsByDate.set(key, {
      date: key,
      total_requests: 0,
      successful_requests: 0,
      failed_requests: 0,
      total_tokens: 0,
      total_cost_usd: 0,
      avg_response_time_ms: 0,
      claude_requests: 0,
      gpt4_requests: 0,
      fallback_requests: 0,
      invalid_category_rejections: 0
    });
  }
  return usageStatsByDate.get(key);
}

function updateUsageStats(response = {}) {
  const stats = getUsageStats();
  const previousTime = stats.avg_response_time_ms * stats.total_requests;
  stats.total_requests += 1;
  if (response.is_reliable) stats.successful_requests += 1;
  else stats.failed_requests += 1;
  stats.total_tokens += Number(response.total_tokens || 0);
  stats.total_cost_usd = Number((stats.total_cost_usd + Number(response.estimated_cost_usd || 0)).toFixed(6));
  stats.avg_response_time_ms = Number(((previousTime + Number(response.response_time_ms || 0)) / stats.total_requests).toFixed(3));
  if (response.provider === "claude") stats.claude_requests += 1;
  else if (response.provider === "gpt4") stats.gpt4_requests += 1;
  else stats.fallback_requests += 1;
  return stats;
}

function incrementInvalidCategory() {
  getUsageStats().invalid_category_rejections += 1;
}

function dailyCostExceeded() {
  return getUsageStats().total_cost_usd >= DAILY_COST_LIMIT_USD;
}

function validateLLMOutput(payload = {}) {
  const categories = Array.isArray(payload.categories) ? payload.categories : [];
  const invalid = categories.filter((category) => !ALLOWED_SET.has(category));
  if (invalid.length) {
    incrementInvalidCategory();
    return { valid: false, error: `İzinsiz kategori: ${invalid.join(", ")}` };
  }
  const uniqueCategories = ALLOWED_CATEGORIES.filter((category) => categories.includes(category));
  const confidences = {};
  const sourceConfidences = payload.confidences && typeof payload.confidences === "object" ? payload.confidences : {};
  for (const [key, value] of Object.entries(sourceConfidences)) {
    if (!ALLOWED_SET.has(key)) {
      incrementInvalidCategory();
      return { valid: false, error: `İzinsiz kategori güven skoru anahtarı: ${key}` };
    }
    const score = Number(value);
    if (!Number.isFinite(score) || score < 0 || score > 1) {
      return { valid: false, error: `Güven skoru 0.0-1.0 arasında olmalı: ${key}` };
    }
    if (uniqueCategories.includes(key)) confidences[key] = Number(score.toFixed(4));
  }
  return {
    valid: true,
    output: {
      categories: uniqueCategories,
      confidences,
      reasoning: safeString(payload.reasoning).split(/\s+/).slice(0, 100).join(" ")
    }
  };
}

function parseAndValidateResponse(rawResponse = "") {
  const cleaned = safeString(rawResponse).replace(/```json\s*/gi, "").replace(/```/g, "").trim();
  if (!cleaned) return { valid: false, error: "Boş LLM yanıtı" };
  try {
    return validateLLMOutput(JSON.parse(cleaned));
  } catch {
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (!match) return { valid: false, error: "JSON parse edilemedi" };
    try {
      return validateLLMOutput(JSON.parse(match[0]));
    } catch {
      return { valid: false, error: "JSON parse edilemedi" };
    }
  }
}

function countKeywordHits(text, keyword) {
  const normalized = normalizeText(text);
  const normalizedKeyword = normalizeText(keyword);
  if (!normalizedKeyword) return 0;
  if (normalizedKeyword.includes(" ")) return normalized.includes(normalizedKeyword) ? 1 : 0;
  const matches = normalized.match(new RegExp(`(^|\\s)${normalizedKeyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?=\\s|$)`, "g"));
  return matches ? matches.length : 0;
}

function ruleBasedFallback(article = {}) {
  const text = [article.title, article.summary, article.description, article.fullText, article.content].filter(Boolean).join("\n").slice(0, MAX_CONTENT_CHARS + 600);
  const normalized = normalizeText(text);
  const started = Date.now();
  if (normalized.length < 20) {
    return {
      categories: [],
      confidences: {},
      reasoning: "Metin boş veya çok kısa olduğu için güvenilir kategori bulunamadı.",
      response_time_ms: Date.now() - started
    };
  }
  const scored = ALLOWED_CATEGORIES.map((category) => {
    let hits = 0;
    const terms = [];
    for (const keyword of KEYWORD_RULES[category] || []) {
      const count = countKeywordHits(text, keyword);
      if (count) {
        hits += count;
        terms.push(keyword);
      }
    }
    return { category, hits, terms };
  }).filter((item) => item.hits >= 2).sort((a, b) => b.hits - a.hits);
  const selected = scored.slice(0, 3).map((item) => item.category);
  const confidences = {};
  for (const item of scored.slice(0, 3)) {
    confidences[item.category] = Number(Math.min(0.75, 0.45 + item.hits * 0.08 + Math.min(0.12, item.terms.length * 0.02)).toFixed(4));
  }
  return {
    categories: selected,
    confidences,
    reasoning: selected.length
      ? "Kural tabanlı fallback, haber metnindeki güvenli anahtar kelime eşleşmelerine göre kategori önerdi."
      : "İzinli kategoriler için yeterli anahtar kelime eşleşmesi bulunamadı.",
    response_time_ms: Date.now() - started
  };
}

function buildSystemPrompt() {
  return `Sen bir haber kategorizasyon uzmanısın.

Sana verilen haber metnini analiz ederek yalnızca izinli kategori listesinden uygun kategorileri seç.

İzinli kategoriler:
${ALLOWED_CATEGORIES.map((category) => `- ${category}`).join("\n")}

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
{"categories":["Kategori1"],"confidences":{"Kategori1":0.95},"reasoning":"Kısa gerekçe"}`;
}

function buildUserPrompt(article = {}, triggerReason = "manual", retryCount = 0) {
  const content = safeString(article.content || article.fullText || article.description || "").slice(0, MAX_CONTENT_CHARS);
  const prompt = `Haber Başlığı:\n${safeString(article.title)}\n\nHaber Özeti:\n${safeString(article.summary)}\n\nHaber İçeriği:\n${content}\n\nDil:\n${safeString(article.detected_lang || article.detectedLang || article.language || "unknown")}\n\nKaynak:\n${safeString(article.sourceName || article.source_name || article.source)}\n\nLLM'e gönderilme nedeni:\n${triggerReason}\n\nMevcut ML tahmini:\n${JSON.stringify({ category: article.category, category_confidence: article.category_confidence, labels: article.labels || [] })}\n\nBu haberi analiz et ve yalnızca izinli kategorilerden uygun olanları JSON formatında döndür.`;
  const warning = retryCount > 0 ? "\n\nÖnemli uyarı: Önceki yanıt geçersizdi. Sadece izinli kategori listesindeki değerleri kullan." : "";
  const full = prompt + warning;
  return estimateTokens(full) <= MAX_PROMPT_TOKENS ? full : `${full.slice(0, MAX_PROMPT_TOKENS * 4)}\n... [prompt token limiti nedeniyle kırpıldı]`;
}

function shouldUseLLM(article = {}, categoryResult = null, multilabelResult = null) {
  const category = categoryResult?.category || article.category;
  const confidence = Number(categoryResult?.confidence ?? categoryResult?.category_confidence ?? article.category_confidence ?? article.categoryConfidence ?? 0);
  const labels = Array.isArray(multilabelResult?.labels) ? multilabelResult.labels : (Array.isArray(article.labels) ? article.labels : []);
  const noLabel = multilabelResult?.no_label_detected ?? article.no_label_detected ?? labels.length === 0;
  if (article.force_llm_validation || article.forceLlmValidation || article.manual_validation_requested) return { use: true, trigger_reason: "manual" };
  if (!Number.isFinite(confidence) || confidence < CATEGORY_CONFIDENCE_THRESHOLD) return { use: true, trigger_reason: "low_confidence" };
  if (noLabel) return { use: true, trigger_reason: "no_label" };
  if (ALLOWED_SET.has(category) && labels.length && !labels.includes(category)) return { use: true, trigger_reason: "model_conflict" };
  if (clusterHasCategoryConflict(article)) return { use: true, trigger_reason: "cluster_conflict" };
  return { use: false, trigger_reason: "" };
}

function clusterHasCategoryConflict(article = {}) {
  const sources = Array.isArray(article.sources) ? article.sources : [];
  const categories = new Set(sources.map((source) => source?.category).filter((category) => ALLOWED_SET.has(category)));
  return categories.size > 1;
}

function buildLLMValidationResponse(article, output, provider, modelName, metadata = {}) {
  const categories = output.categories || [];
  const confidences = output.confidences || {};
  const promptTokens = Number(metadata.prompt_tokens || 0);
  const completionTokens = Number(metadata.completion_tokens || 0);
  const totalTokens = promptTokens + completionTokens;
  const response = {
    used: true,
    trigger_reason: metadata.trigger_reason || "manual",
    provider,
    model_name: modelName,
    predicted_labels: categories,
    label_confidences: confidences,
    reasoning: output.reasoning || "",
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    total_tokens: totalTokens,
    estimated_cost_usd: calculateCost(provider, promptTokens, completionTokens),
    is_reliable: categories.length > 0 && Math.max(0, ...Object.values(confidences).map(Number)) >= 0.7,
    no_label_detected: categories.length === 0,
    retry_count: Number(metadata.retry_count || 0),
    response_time_ms: Number(metadata.response_time_ms || output.response_time_ms || 0),
    raw_response: metadata.raw_response || JSON.stringify(output),
    created_at: new Date().toISOString()
  };
  updateUsageStats(response);
  if (!response.is_reliable || response.no_label_detected) addAdminQueueItem(article, response);
  return response;
}

function addAdminQueueItem(article = {}, llmValidation = {}) {
  const item = {
    article_id: String(article.id || article.article_id || article.url || "unknown"),
    cluster_id: article.cluster_id || article.clusterId || null,
    title: article.title || "Başlıksız haber",
    trigger_reason: llmValidation.trigger_reason || "manual",
    ml_prediction: { category: article.category, category_confidence: article.category_confidence, labels: article.labels || [] },
    llm_prediction: llmValidation,
    created_at: new Date().toISOString()
  };
  adminQueue.unshift(item);
  if (adminQueue.length > 500) adminQueue.pop();
  return item;
}

async function callClaude(article, triggerReason, retryCount = 0) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not configured");
  if (typeof fetch !== "function") throw new Error("fetch is not available for Claude provider");
  const system = buildSystemPrompt();
  const user = buildUserPrompt(article, triggerReason, retryCount);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = Date.now();
  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      signal: controller.signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: PROVIDER_MODELS.claude,
        max_tokens: 512,
        temperature: 0,
        system,
        messages: [{ role: "user", content: user }]
      })
    });
    if (!response.ok) throw new Error(`Claude HTTP ${response.status}`);
    const data = await response.json();
    const raw = Array.isArray(data.content) ? data.content.map((block) => block.text || "").join("") : "";
    return {
      raw_response: raw,
      prompt_tokens: Number(data.usage?.input_tokens || estimateTokens(system + user)),
      completion_tokens: Number(data.usage?.output_tokens || estimateTokens(raw)),
      response_time_ms: Date.now() - started
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function callOpenAI(article, triggerReason, retryCount = 0) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not configured");
  if (typeof fetch !== "function") throw new Error("fetch is not available for OpenAI provider");
  const system = buildSystemPrompt();
  const user = buildUserPrompt(article, triggerReason, retryCount);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = Date.now();
  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      signal: controller.signal,
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: PROVIDER_MODELS.gpt4,
        max_tokens: 512,
        temperature: 0,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user }
        ]
      })
    });
    if (!response.ok) throw new Error(`OpenAI HTTP ${response.status}`);
    const data = await response.json();
    const raw = data.choices?.[0]?.message?.content || "";
    return {
      raw_response: raw,
      prompt_tokens: Number(data.usage?.prompt_tokens || estimateTokens(system + user)),
      completion_tokens: Number(data.usage?.completion_tokens || estimateTokens(raw)),
      response_time_ms: Date.now() - started
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function callProviderWithValidation(provider, article, triggerReason) {
  for (let retryCount = 0; retryCount <= MAX_RETRIES; retryCount += 1) {
    const raw = provider === "claude"
      ? await callClaude(article, triggerReason, retryCount)
      : await callOpenAI(article, triggerReason, retryCount);
    const parsed = parseAndValidateResponse(raw.raw_response);
    if (parsed.valid) {
      return buildLLMValidationResponse(article, parsed.output, provider, PROVIDER_MODELS[provider], {
        ...raw,
        trigger_reason: triggerReason,
        retry_count: retryCount,
        raw_response: raw.raw_response
      });
    }
  }
  throw new Error(`${provider} returned invalid output`);
}

async function categorizeArticle(article = {}, options = {}) {
  const trigger = options.trigger_reason || options.triggerReason || shouldUseLLM(article).trigger_reason || "manual";
  const triggerReason = TRIGGER_REASONS.has(trigger) ? trigger : "manual";
  const cacheKey = cacheKeyForArticle(article);
  const cached = getCached(cacheKey);
  if (cached) return cached;

  const enabled = String(process.env.LLM_CATEGORIZER_ENABLED || "true").toLowerCase() !== "false";
  const providers = (process.env.LLM_PRIMARY_PROVIDER || "claude").toLowerCase() === "gpt4" ? ["gpt4", "claude"] : ["claude", "gpt4"];

  if (enabled && !dailyCostExceeded() && normalizeText(articleText(article)).length >= 20) {
    for (const provider of providers) {
      try {
        const response = await callProviderWithValidation(provider, article, triggerReason);
        setCached(cacheKey, response);
        return response;
      } catch (error) {
        if (process.env.NODE_ENV !== "test") console.warn(`[llm-categorizer] ${provider} failed: ${error.message}`);
      }
    }
  }

  const fallback = ruleBasedFallback(article);
  const response = buildLLMValidationResponse(article, fallback, "fallback", PROVIDER_MODELS.fallback, {
    trigger_reason: triggerReason,
    response_time_ms: fallback.response_time_ms,
    raw_response: JSON.stringify({ categories: fallback.categories, confidences: fallback.confidences, reasoning: fallback.reasoning })
  });
  setCached(cacheKey, response);
  return response;
}

async function categorizeArticles(articles = [], options = {}) {
  const maxConcurrent = Math.max(1, Math.min(10, Number(options.max_concurrent || options.maxConcurrent || process.env.LLM_BATCH_MAX_CONCURRENT || 5) || 5));
  const source = Array.isArray(articles) ? articles : [];
  const results = [];
  let cursor = 0;
  async function worker() {
    while (cursor < source.length) {
      const index = cursor;
      cursor += 1;
      try {
        results[index] = await categorizeArticle(source[index], options);
      } catch (error) {
        const fallback = ruleBasedFallback(source[index]);
        results[index] = buildLLMValidationResponse(source[index], fallback, "fallback", PROVIDER_MODELS.fallback, {
          trigger_reason: options.trigger_reason || "manual",
          raw_response: JSON.stringify(fallback)
        });
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(maxConcurrent, source.length || 1) }, () => worker()));
  return results;
}

function applyLLMValidationToArticleSync(article = {}, options = {}) {
  if (!article || typeof article !== "object") return article;
  const decision = shouldUseLLM(article);
  if (!decision.use && !options.force) {
    article.llm_validation = article.llm_validation || { used: false, trigger_reason: "not_needed", provider: "none", is_reliable: true, no_label_detected: false };
    article.llmValidation = article.llm_validation;
    return article;
  }
  const fallback = ruleBasedFallback(article);
  const response = buildLLMValidationResponse(article, fallback, "fallback", PROVIDER_MODELS.fallback, {
    trigger_reason: options.trigger_reason || decision.trigger_reason || "manual",
    response_time_ms: fallback.response_time_ms,
    raw_response: JSON.stringify(fallback)
  });
  article.llm_validation = response;
  article.llmValidation = response;
  if (response.is_reliable) mergeLLMLabels(article, response);
  if (Array.isArray(article.sources)) {
    article.sources = article.sources.map((source) => {
      if (!source || typeof source !== "object") return source;
      const sourceArticle = { ...article, ...source, title: source.title || article.title, summary: source.summary || article.summary };
      const sourceFallback = ruleBasedFallback(sourceArticle);
      const sourceValidation = buildLLMValidationResponse(sourceArticle, sourceFallback, "fallback", PROVIDER_MODELS.fallback, {
        trigger_reason: options.trigger_reason || decision.trigger_reason || "manual",
        response_time_ms: sourceFallback.response_time_ms,
        raw_response: JSON.stringify(sourceFallback)
      });
      const enrichedSource = { ...source, llm_validation: sourceValidation, llmValidation: sourceValidation };
      if (sourceValidation.is_reliable) mergeLLMLabels(enrichedSource, sourceValidation);
      return enrichedSource;
    });
  }
  return article;
}

function mergeLLMLabels(target, response) {
  const incoming = Array.isArray(response.predicted_labels) ? response.predicted_labels : [];
  const current = Array.isArray(target.labels) ? target.labels : [];
  const merged = ALLOWED_CATEGORIES.filter((category) => current.includes(category) || incoming.includes(category));
  target.labels = merged;
  target.label_scores = { ...(target.label_scores || {}) };
  for (const [label, score] of Object.entries(response.label_confidences || {})) {
    if (ALLOWED_SET.has(label)) target.label_scores[label] = Math.max(Number(target.label_scores[label] || 0), Number(score || 0));
  }
  target.label_vector = ALLOWED_CATEGORIES.map((category) => merged.includes(category) ? 1 : 0);
  target.no_label_detected = merged.length === 0;
  target.is_multilabel_reliable = target.is_multilabel_reliable || response.is_reliable;
  target.num_labels = ALLOWED_CATEGORIES.length;
  return target;
}

function getAdminQueue() {
  return [...adminQueue];
}

function buildLLMCategorizerStats(articles = []) {
  const validations = (Array.isArray(articles) ? articles : []).map((article) => article?.llm_validation || article?.llmValidation).filter(Boolean);
  return {
    totalArticles: Array.isArray(articles) ? articles.length : 0,
    validationUsed: validations.filter((item) => item.used).length,
    reliable: validations.filter((item) => item.is_reliable).length,
    adminQueueSize: adminQueue.length,
    usage: getUsageStats(),
    cacheSize: responseCache.size,
    generatedAt: new Date().toISOString()
  };
}

const LLM_CATEGORIZER_CONFIG = Object.freeze({
  allowedCategories: ALLOWED_CATEGORIES,
  numCategories: ALLOWED_CATEGORIES.length,
  triggerReasons: [...TRIGGER_REASONS],
  maxRetries: MAX_RETRIES,
  cacheTtlSeconds: Math.round(CACHE_TTL_MS / 1000),
  cacheMaxSize: CACHE_MAX_SIZE,
  maxContentChars: MAX_CONTENT_CHARS,
  maxPromptTokens: MAX_PROMPT_TOKENS,
  primaryProvider: process.env.LLM_PRIMARY_PROVIDER || "claude",
  fallbackProvider: "rule-based",
  dailyCostLimitUsd: DAILY_COST_LIMIT_USD,
  pricing: PRICING
});

module.exports = {
  ALLOWED_CATEGORIES,
  KEYWORD_RULES,
  LLM_CATEGORIZER_CONFIG,
  calculateCost,
  parseAndValidateResponse,
  validateLLMOutput,
  ruleBasedFallback,
  buildSystemPrompt,
  buildUserPrompt,
  shouldUseLLM,
  categorizeArticle,
  categorizeArticles,
  applyLLMValidationToArticleSync,
  mergeLLMLabels,
  getAdminQueue,
  getUsageStats,
  buildLLMCategorizerStats,
  _internal: { responseCache, adminQueue, usageStatsByDate, cacheKeyForArticle, clusterHasCategoryConflict }
};
