const crypto = require("crypto");

const MAX_QUERY_LENGTH = 150;
const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;
const TREND_WEIGHTS = Object.freeze({
  recentViews: 0.40,
  recentShares: 0.30,
  searchClicks: 0.20,
  freshness: 0.10
});

const SEARCH_CATEGORY_MAP = Object.freeze({
  gundem: { type: "special", value: "trend_or_latest" },
  "gündem": { type: "special", value: "trend_or_latest" },
  politika: { type: "label", value: "Siyaset" },
  siyaset: { type: "label", value: "Siyaset" },
  magazin: { type: "label", value: "Eğlence" },
  eglence: { type: "label", value: "Eğlence" },
  "eğlence": { type: "label", value: "Eğlence" },
  saglik: { type: "label", value: "Sağlık" },
  "sağlık": { type: "label", value: "Sağlık" },
  spor: { type: "label", value: "Spor" },
  teknoloji: { type: "label", value: "Teknoloji" },
  ekonomi: { type: "label", value: "Ekonomi" },
  bilim: { type: "label", value: "Bilim" },
  dunya: { type: "label", value: "Dünya" },
  "dünya": { type: "label", value: "Dünya" },
  yasam: { type: "label", value: "Yaşam" },
  "yaşam": { type: "label", value: "Yaşam" }
});

const STOP_WORDS = new Set([
  "ve", "veya", "ile", "bir", "bu", "şu", "su", "da", "de", "için", "icin", "olan", "olarak", "son", "yeni", "haber",
  "the", "and", "or", "for", "of", "in", "on", "to", "a", "an"
]);

function normalizeTurkishText(text = "") {
  return String(text || "")
    .toLocaleLowerCase("tr-TR")
    .normalize("NFKC")
    .replace(/[’']/g, "")
    .replace(/ç/g, "c")
    .replace(/ğ/g, "g")
    .replace(/ı/g, "i")
    .replace(/ö/g, "o")
    .replace(/ş/g, "s")
    .replace(/ü/g, "u")
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sanitizeQuery(query = "") {
  const raw = String(query || "").replace(/[<>`$\\]/g, " ").replace(/\s+/g, " ").trim();
  return raw.slice(0, MAX_QUERY_LENGTH);
}

function tokenStem(token = "") {
  let value = normalizeTurkishText(token);
  const suffixes = [
    "lerinden", "larindan", "lerinden", "lerinden", "lerin", "ların", "lari", "leri", "lerde", "larda",
    "inden", "dan", "den", "dir", "dır", "dur", "dür", "lar", "ler", "nin", "nın", "nun", "nün", "in", "un", "ın", "ün", "de", "da", "e", "a"
  ].map(normalizeTurkishText);
  for (const suffix of suffixes) {
    if (value.length > suffix.length + 3 && value.endsWith(suffix)) return value.slice(0, -suffix.length);
  }
  return value;
}

function tokenize(text = "") {
  return normalizeTurkishText(text)
    .split(/\s+/)
    .map(tokenStem)
    .filter((token) => token.length >= 2 && !STOP_WORDS.has(token));
}

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

function getArticleId(article = {}) {
  return String(firstDefined(article.id, article.article_id, article.articleId, article.guid, article.url, article.sourceUrl, "")).trim();
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

function toDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getArticleDateMs(article = {}) {
  const date = toDate(getArticlePublishedAt(article));
  return date ? date.getTime() : 0;
}

function getArticleSources(article = {}) {
  const sources = [];
  const nested = [
    ...asArray(article.sources),
    ...asArray(article.relatedSources),
    ...asArray(article.clusterArticles)
  ];
  for (const source of nested) {
    if (source && typeof source === "object") sources.push(source);
  }
  const sourceName = getArticleSourceName(article);
  if (sourceName) {
    sources.unshift({
      source_name: sourceName,
      sourceName,
      title: getArticleTitle(article),
      source_url: firstDefined(article.source_url, article.sourceUrl, article.url, ""),
      sourceUrl: firstDefined(article.source_url, article.sourceUrl, article.url, "")
    });
  }
  const seen = new Set();
  return sources.filter((source) => {
    const key = normalizeTurkishText(firstDefined(source.source_name, source.sourceName, source.source, source.publisher, source.title, ""));
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
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

function getSourceNames(article = {}) {
  return getArticleSources(article)
    .map((source) => firstDefined(source.source_name, source.sourceName, source.source, source.publisher, source.newspaper, source.rss_source, ""))
    .filter(Boolean)
    .map(String);
}

function buildSearchableText(article = {}) {
  return [
    getArticleTitle(article),
    getArticleSummary(article),
    getArticleContent(article),
    getArticleLabels(article).join(" "),
    getArticleSourceName(article),
    getSourceNames(article).join(" ")
  ].join(" ");
}

function fieldMatches(fieldValue, queryTokens) {
  const fieldText = normalizeTurkishText(fieldValue || "");
  if (!fieldText || !queryTokens.length) return { count: 0, exactPhrase: false };
  const fieldTokens = new Set(tokenize(fieldText));
  let count = 0;
  for (const token of queryTokens) {
    if (fieldTokens.has(token)) count += 1;
    else if ([...fieldTokens].some((candidate) => candidate.startsWith(token) || token.startsWith(candidate))) count += 0.65;
  }
  return { count, exactPhrase: false };
}

function calculateSearchScore(article = {}, rawQuery = "") {
  const sanitized = sanitizeQuery(rawQuery);
  const normalizedQuery = normalizeTurkishText(sanitized);
  if (!normalizedQuery) return 0;
  const queryTokens = tokenize(normalizedQuery);
  if (!queryTokens.length) return 0;
  const titleScore = fieldMatches(getArticleTitle(article), queryTokens).count * 4;
  const labelsScore = fieldMatches(getArticleLabels(article).join(" "), queryTokens).count * 3;
  const summaryScore = fieldMatches(getArticleSummary(article), queryTokens).count * 2;
  const contentScore = fieldMatches(getArticleContent(article).slice(0, 2500), queryTokens).count * 1;
  const sourceScore = fieldMatches(getSourceNames(article).join(" "), queryTokens).count * 0.5;
  const phraseBoost = normalizeTurkishText(buildSearchableText(article)).includes(normalizedQuery) ? 5 : 0;
  const raw = titleScore + labelsScore + summaryScore + contentScore + sourceScore + phraseBoost;
  const max = Math.max(1, queryTokens.length * 10 + 5);
  return Math.min(100, Math.round((raw / max) * 10000) / 100);
}

function normalizeCategoryFilter(category = "") {
  const normalized = normalizeTurkishText(category);
  return SEARCH_CATEGORY_MAP[normalized] || (normalized ? { type: "label", value: String(category).trim() } : null);
}

function articleMatchesCategory(article = {}, category = "") {
  const mapped = normalizeCategoryFilter(category);
  if (!mapped) return true;
  if (mapped.type === "special") {
    return Boolean(article.is_trending || article.isTrending)
      || Number(article.trend_score || article.trendScore || 0) >= 50
      || Number(article.headline_score || article.headlineScore || 0) >= 60
      || Number(article.importance_score || article.importanceScore || 0) >= 0.7
      || Number(article.source_count || article.sourceCount || getArticleSources(article).length || 0) >= 3;
  }
  const wanted = normalizeTurkishText(mapped.value);
  return getArticleLabels(article).some((label) => normalizeTurkishText(label) === wanted);
}

function articleMatchesSource(article = {}, source = "") {
  const wanted = normalizeTurkishText(source);
  if (!wanted) return true;
  return getSourceNames(article).some((name) => normalizeTurkishText(name) === wanted);
}

function buildDateRange({ dateFilter = "", startDate = "", endDate = "", now = new Date() } = {}) {
  const warnings = [];
  let start = null;
  let end = null;
  const filter = String(dateFilter || "").toLowerCase();
  const todayStart = new Date(now);
  todayStart.setHours(0, 0, 0, 0);
  if (filter === "today") {
    start = todayStart;
    end = new Date(todayStart);
    end.setHours(23, 59, 59, 999);
  } else if (filter === "this_week") {
    start = new Date(todayStart);
    const day = (start.getDay() + 6) % 7;
    start.setDate(start.getDate() - day);
    end = now;
  } else if (filter === "this_month") {
    start = new Date(todayStart.getFullYear(), todayStart.getMonth(), 1);
    end = now;
  }
  if (startDate || endDate) {
    const parsedStart = startDate ? toDate(`${startDate}T00:00:00`) : null;
    const parsedEnd = endDate ? toDate(`${endDate}T23:59:59`) : null;
    if (startDate && !parsedStart) warnings.push("Geçersiz başlangıç tarihi yok sayıldı.");
    if (endDate && !parsedEnd) warnings.push("Geçersiz bitiş tarihi yok sayıldı.");
    if (parsedStart) start = parsedStart;
    if (parsedEnd) end = parsedEnd;
  }
  return { start, end, warnings };
}

function articleMatchesDate(article = {}, dateRange = {}) {
  if (!dateRange.start && !dateRange.end) return true;
  const date = toDate(getArticlePublishedAt(article));
  if (!date) return false;
  if (dateRange.start && date < dateRange.start) return false;
  if (dateRange.end && date > dateRange.end) return false;
  return true;
}

function calculateFreshnessScore(publishedAt, now = new Date()) {
  const published = toDate(publishedAt);
  if (!published) return 10;
  const hoursOld = Math.max(0, (now.getTime() - published.getTime()) / 36e5);
  if (hoursOld <= 1) return 100;
  if (hoursOld <= 6) return 90;
  if (hoursOld <= 24) return 75;
  if (hoursOld <= 72) return 50;
  if (hoursOld <= 168) return 30;
  return 10;
}

function normalizeNumber(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? Math.max(0, number) : 0;
}

function initSearchDb(db = {}) {
  db.searchLogs = Array.isArray(db.searchLogs) ? db.searchLogs : [];
  db.newsInteractions = Array.isArray(db.newsInteractions) ? db.newsInteractions : [];
  for (const article of Array.isArray(db.articles) ? db.articles : []) normalizeSearchArticleFields(article);
  return db;
}

function normalizeSearchArticleFields(article = {}) {
  article.view_count = normalizeNumber(firstDefined(article.view_count, article.viewCount, article.read_count, article.click_count, 0));
  article.share_count = normalizeNumber(firstDefined(article.share_count, article.shareCount, 0));
  article.search_count = normalizeNumber(firstDefined(article.search_count, article.searchCount, 0));
  article.search_click_count = normalizeNumber(firstDefined(article.search_click_count, article.searchClickCount, 0));
  article.trend_score = normalizeNumber(firstDefined(article.trend_score, article.trendScore, 0));
  article.viewCount = article.view_count;
  article.shareCount = article.share_count;
  article.searchCount = article.search_count;
  article.searchClickCount = article.search_click_count;
  article.trendScore = article.trend_score;
  article.source_name = article.source_name || article.sourceName || article.source || "";
  article.published_at = article.published_at || article.publishedAt || article.pubDate || article.date || article.fetchedAt || article.createdAt || "";
  return article;
}

function getArticlePool(db = {}, extraArticles = []) {
  const byId = new Map();
  for (const article of [...(Array.isArray(db.articles) ? db.articles : []), ...(Array.isArray(extraArticles) ? extraArticles : [])]) {
    if (!article || typeof article !== "object") continue;
    const id = getArticleId(article);
    if (!id) continue;
    byId.set(id, normalizeSearchArticleFields(article));
  }
  return [...byId.values()];
}

function normalizeSearchParams(params = {}) {
  const q = sanitizeQuery(params.q || params.query || "");
  const page = Math.max(1, Number.parseInt(params.page || "1", 10) || 1);
  const limit = Math.min(MAX_LIMIT, Math.max(1, Number.parseInt(params.limit || DEFAULT_LIMIT, 10) || DEFAULT_LIMIT));
  return {
    q,
    normalizedQuery: normalizeTurkishText(q),
    category: sanitizeQuery(params.category || ""),
    source: sanitizeQuery(params.source || ""),
    startDate: sanitizeQuery(params.startDate || ""),
    endDate: sanitizeQuery(params.endDate || ""),
    dateFilter: sanitizeQuery(params.dateFilter || ""),
    sort: sanitizeQuery(params.sort || "").toLowerCase() || (q ? "relevance" : "newest"),
    page,
    limit,
    offset: (page - 1) * limit
  };
}

function applySearchFilters(articles = [], filters = {}) {
  const dateRange = buildDateRange(filters);
  let list = articles.filter((article) => articleMatchesDate(article, dateRange));
  if (filters.category) list = list.filter((article) => articleMatchesCategory(article, filters.category));
  if (filters.source) list = list.filter((article) => articleMatchesSource(article, filters.source));
  return { articles: list, warnings: dateRange.warnings || [] };
}

function sortSearchResults(articles = [], sort = "relevance") {
  const mode = String(sort || "relevance").toLowerCase();
  const dateDesc = (a, b) => getArticleDateMs(b) - getArticleDateMs(a);
  if (mode === "most_read") return articles.sort((a, b) => normalizeNumber(b.view_count) - normalizeNumber(a.view_count) || dateDesc(a, b));
  if (mode === "most_shared") return articles.sort((a, b) => normalizeNumber(b.share_count) - normalizeNumber(a.share_count) || dateDesc(a, b));
  if (mode === "newest" || mode === "latest") return articles.sort(dateDesc);
  if (mode === "trend") return articles.sort((a, b) => normalizeNumber(b.trend_score) - normalizeNumber(a.trend_score) || dateDesc(a, b));
  return articles.sort((a, b) => normalizeNumber(b.score) - normalizeNumber(a.score) || dateDesc(a, b));
}

function serializeArticle(article = {}, extra = {}) {
  const sources = getArticleSources(article);
  return {
    ...article,
    id: getArticleId(article),
    title: getArticleTitle(article),
    summary: getArticleSummary(article),
    content: getArticleContent(article),
    source_name: getArticleSourceName(article),
    sourceName: getArticleSourceName(article),
    published_at: getArticlePublishedAt(article),
    publishedAt: getArticlePublishedAt(article),
    labels: asArray(article.labels).length ? asArray(article.labels) : getArticleLabels(article),
    sources: Array.isArray(article.sources) ? article.sources : sources,
    source_count: normalizeNumber(firstDefined(article.source_count, article.sourceCount, sources.length || 1)),
    sourceCount: normalizeNumber(firstDefined(article.source_count, article.sourceCount, sources.length || 1)),
    view_count: normalizeNumber(article.view_count),
    share_count: normalizeNumber(article.share_count),
    search_count: normalizeNumber(article.search_count),
    search_click_count: normalizeNumber(article.search_click_count),
    trend_score: Math.round(normalizeNumber(article.trend_score) * 100) / 100,
    trendScore: Math.round(normalizeNumber(article.trend_score) * 100) / 100,
    image_url: firstDefined(article.image_url, article.imageUrl, article.image, ""),
    imageUrl: firstDefined(article.imageUrl, article.image_url, article.image, ""),
    url: firstDefined(article.url, article.sourceUrl, article.source_url, ""),
    score: Math.round(normalizeNumber(extra.score ?? article.score) * 100) / 100,
    ...extra
  };
}

function logSearch(db = {}, { userId = "anonymous", query = "", normalizedQuery = "", resultCount = 0 } = {}) {
  initSearchDb(db);
  const entry = {
    id: `search_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    user_id: String(userId || "anonymous"),
    userId: String(userId || "anonymous"),
    query: String(query || "").slice(0, MAX_QUERY_LENGTH),
    normalized_query: String(normalizedQuery || "").slice(0, MAX_QUERY_LENGTH),
    normalizedQuery: String(normalizedQuery || "").slice(0, MAX_QUERY_LENGTH),
    result_count: Number(resultCount || 0),
    resultCount: Number(resultCount || 0),
    clicked_news_id: "",
    clickedNewsId: "",
    created_at: new Date().toISOString(),
    createdAt: new Date().toISOString()
  };
  db.searchLogs.push(entry);
  if (db.searchLogs.length > 5000) db.searchLogs = db.searchLogs.slice(-5000);
  return entry;
}

function searchArticles(db = {}, params = {}, options = {}) {
  initSearchDb(db);
  const filters = normalizeSearchParams(params);
  const pool = getArticlePool(db, options.extraArticles || []);
  const query = filters.q;
  let scored = pool.map((article) => {
    const score = query ? calculateSearchScore(article, query) : 0;
    return { article, score };
  });
  if (query) scored = scored.filter((item) => item.score > 0);
  let filtered = scored.map((item) => ({ ...item.article, score: item.score }));
  const filterResult = applySearchFilters(filtered, filters);
  filtered = filterResult.articles;
  const sorted = sortSearchResults(filtered, filters.sort);
  const total = sorted.length;
  const pageItems = sorted.slice(filters.offset, filters.offset + filters.limit).map((article) => serializeArticle(article, { score: article.score }));
  if (options.log !== false) logSearch(db, { userId: options.userId, query: filters.q, normalizedQuery: filters.normalizedQuery, resultCount: total });
  return {
    success: true,
    query: filters.q,
    normalizedQuery: filters.normalizedQuery,
    filters: {
      category: filters.category,
      source: filters.source,
      startDate: filters.startDate,
      endDate: filters.endDate,
      dateFilter: filters.dateFilter,
      sort: filters.sort
    },
    warnings: filterResult.warnings,
    total,
    count: pageItems.length,
    page: filters.page,
    limit: filters.limit,
    hasMore: filters.offset + filters.limit < total,
    data: pageItems
  };
}

function listSearchSources(db = {}, extraArticles = []) {
  const sources = new Set();
  for (const article of getArticlePool(db, extraArticles)) {
    for (const name of getSourceNames(article)) if (name) sources.add(name);
  }
  return [...sources].sort((a, b) => a.localeCompare(b, "tr"));
}

function buildSearchSuggestions(db = {}, query = "", limit = 8) {
  const q = normalizeTurkishText(sanitizeQuery(query));
  if (!q) return [];
  const suggestions = new Map();
  const add = (value, weight = 1) => {
    const text = String(value || "").trim();
    if (!text || text.length > 80) return;
    if (!normalizeTurkishText(text).includes(q)) return;
    suggestions.set(text, (suggestions.get(text) || 0) + weight);
  };
  for (const log of Array.isArray(db.searchLogs) ? db.searchLogs : []) add(log.query, 3);
  for (const article of getArticlePool(db)) {
    add(getArticleTitle(article), 2);
    for (const label of getArticleLabels(article)) add(label, 2.5);
    for (const source of getSourceNames(article)) add(source, 1.5);
  }
  ["ekonomi", "enflasyon", "Merkez Bankası", "teknoloji", "deprem", "seçim", "spor", "sağlık"].forEach((item) => add(item, 1));
  return [...suggestions.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "tr")).slice(0, limit).map(([value]) => value);
}

function recordNewsInteraction(db = {}, articleId = "", userId = "anonymous", interactionType = "view", meta = {}) {
  initSearchDb(db);
  const type = ["view", "share", "search_click"].includes(interactionType) ? interactionType : "view";
  const id = String(articleId || "").trim();
  if (!id) throw new Error("Haber kimliği gerekli.");
  const article = getArticlePool(db).find((item) => getArticleId(item) === id);
  if (!article) throw new Error("Haber bulunamadı.");
  const now = new Date().toISOString();
  db.newsInteractions.push({
    id: `interaction_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    news_id: id,
    newsId: id,
    user_id: String(userId || "anonymous"),
    userId: String(userId || "anonymous"),
    interaction_type: type,
    interactionType: type,
    created_at: now,
    createdAt: now,
    session_id: meta.sessionId || "",
    sessionId: meta.sessionId || ""
  });
  if (db.newsInteractions.length > 20000) db.newsInteractions = db.newsInteractions.slice(-20000);
  if (type === "view") article.view_count = normalizeNumber(article.view_count) + 1;
  if (type === "share") article.share_count = normalizeNumber(article.share_count) + 1;
  if (type === "search_click") {
    article.search_click_count = normalizeNumber(article.search_click_count) + 1;
    const lastSearch = [...(db.searchLogs || [])].reverse().find((log) => log.user_id === String(userId || "anonymous") && !log.clicked_news_id);
    if (lastSearch) {
      lastSearch.clicked_news_id = id;
      lastSearch.clickedNewsId = id;
    }
  }
  article.viewCount = article.view_count;
  article.shareCount = article.share_count;
  article.searchClickCount = article.search_click_count;
  return { success: true, article: serializeArticle(article), interactionType: type };
}

function recentInteractionCounts(db = {}, since = new Date(Date.now() - 86400000)) {
  const counts = new Map();
  for (const interaction of Array.isArray(db.newsInteractions) ? db.newsInteractions : []) {
    const created = toDate(interaction.created_at || interaction.createdAt);
    if (!created || created < since) continue;
    const id = String(interaction.news_id || interaction.newsId || "");
    if (!id) continue;
    const row = counts.get(id) || { views: 0, shares: 0, searchClicks: 0 };
    if (interaction.interaction_type === "view" || interaction.interactionType === "view") row.views += 1;
    if (interaction.interaction_type === "share" || interaction.interactionType === "share") row.shares += 1;
    if (interaction.interaction_type === "search_click" || interaction.interactionType === "search_click") row.searchClicks += 1;
    counts.set(id, row);
  }
  return counts;
}

function calculateTrendScores(db = {}, options = {}) {
  initSearchDb(db);
  const now = options.now || new Date();
  const since = new Date(now.getTime() - 86400000);
  const allPool = getArticlePool(db);
  let articles = allPool.filter((article) => {
    const published = toDate(getArticlePublishedAt(article));
    return !published || published >= since;
  });
  if (!articles.length) articles = allPool.slice();
  const counts = recentInteractionCounts(db, since);
  const fallbackCounts = articles.map((article) => {
    const id = getArticleId(article);
    const recent = counts.get(id) || { views: 0, shares: 0, searchClicks: 0 };
    return {
      id,
      views: recent.views || Math.min(normalizeNumber(article.view_count), 20),
      shares: recent.shares || Math.min(normalizeNumber(article.share_count), 20),
      searchClicks: recent.searchClicks || Math.min(normalizeNumber(article.search_click_count), 20)
    };
  });
  const maxViews = Math.max(0, ...fallbackCounts.map((item) => item.views));
  const maxShares = Math.max(0, ...fallbackCounts.map((item) => item.shares));
  const maxSearchClicks = Math.max(0, ...fallbackCounts.map((item) => item.searchClicks));
  const byId = new Map(fallbackCounts.map((item) => [item.id, item]));
  for (const article of articles) {
    const id = getArticleId(article);
    const row = byId.get(id) || { views: 0, shares: 0, searchClicks: 0 };
    const normalizedRecentViews = maxViews > 0 ? (row.views / maxViews) * 100 : 0;
    const normalizedRecentShares = maxShares > 0 ? (row.shares / maxShares) * 100 : 0;
    const normalizedSearchClicks = maxSearchClicks > 0 ? (row.searchClicks / maxSearchClicks) * 100 : 0;
    const freshness = calculateFreshnessScore(getArticlePublishedAt(article), now);
    const trendScore = normalizedRecentViews * TREND_WEIGHTS.recentViews
      + normalizedRecentShares * TREND_WEIGHTS.recentShares
      + normalizedSearchClicks * TREND_WEIGHTS.searchClicks
      + freshness * TREND_WEIGHTS.freshness;
    article.recent_views = row.views;
    article.recent_shares = row.shares;
    article.recent_search_clicks = row.searchClicks;
    article.trend_score = Math.round(trendScore * 100) / 100;
    article.trendScore = article.trend_score;
  }
  return articles.map((article) => serializeArticle(article, {
    recent_views: normalizeNumber(article.recent_views),
    recent_shares: normalizeNumber(article.recent_shares),
    recent_search_clicks: normalizeNumber(article.recent_search_clicks)
  })).sort((a, b) => normalizeNumber(b.trend_score) - normalizeNumber(a.trend_score) || getArticleDateMs(b) - getArticleDateMs(a));
}

function getTrends(db = {}, params = {}) {
  const filters = normalizeSearchParams({ ...params, sort: "trend", page: 1, limit: params.limit || 10 });
  const computed = calculateTrendScores(db);
  const filterResult = applySearchFilters(computed, filters);
  const sorted = sortSearchResults(filterResult.articles, "trend");
  const limit = filters.limit;
  return {
    success: true,
    period: "last_24_hours",
    filters: {
      category: filters.category,
      source: filters.source,
      dateFilter: filters.dateFilter || "last_24_hours"
    },
    count: Math.min(limit, sorted.length),
    total: sorted.length,
    data: sorted.slice(0, limit).map((article) => serializeArticle(article, {
      recent_views: normalizeNumber(article.recent_views),
      recent_shares: normalizeNumber(article.recent_shares),
      search_click_count: normalizeNumber(article.search_click_count)
    }))
  };
}

module.exports = {
  MAX_QUERY_LENGTH,
  SEARCH_CATEGORY_MAP,
  TREND_WEIGHTS,
  normalizeTurkishText,
  sanitizeQuery,
  tokenize,
  tokenStem,
  normalizeSearchArticleFields,
  initSearchDb,
  getArticlePool,
  calculateSearchScore,
  searchArticles,
  listSearchSources,
  buildSearchSuggestions,
  recordNewsInteraction,
  calculateFreshnessScore,
  calculateTrendScores,
  getTrends,
  normalizeSearchParams,
  applySearchFilters,
  articleMatchesCategory,
  articleMatchesSource,
  serializeArticle
};
