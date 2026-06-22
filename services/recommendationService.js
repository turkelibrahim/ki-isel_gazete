"use strict";

const AnalyticsService = require("./analyticsService");
const VectorService = require("./vectorService");

const DEFAULT_LIMIT = 12;
const MAX_LIMIT = 50;

function toNumber(value, fallback = 0) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function clamp(n, min, max) { return Math.min(max, Math.max(min, toNumber(n, min))); }
function nowIso() { return new Date().toISOString(); }
function asArray(value) { return VectorService.asArray(value); }

function normalizeDb(db = {}) {
  AnalyticsService.normalizeDb(db);
  return db;
}

function getArticleDate(article = {}) {
  const value = VectorService.getArticlePublishedAt(article);
  const date = new Date(value || 0);
  return Number.isNaN(date.getTime()) ? null : date;
}

function calculateFreshnessScore(article = {}, now = new Date()) {
  const date = getArticleDate(article);
  if (!date) return 10;
  const hoursOld = Math.max(0, (now.getTime() - date.getTime()) / 3600000);
  if (hoursOld <= 6) return 100;
  if (hoursOld <= 24) return 80;
  if (hoursOld <= 72) return 55;
  if (hoursOld <= 168) return 30;
  return 10;
}

function calculatePopularityScore(article = {}, maxViewCount = 0, maxShareCount = 0) {
  const views = toNumber(article.view_count || article.viewCount || article.read_count || article.click_count, 0);
  const shares = toNumber(article.share_count || article.shareCount, 0);
  const normalizedViews = maxViewCount > 0 ? (views / maxViewCount) * 100 : 0;
  const normalizedShares = maxShareCount > 0 ? (shares / maxShareCount) * 100 : 0;
  return Math.round((normalizedViews * 0.60 + normalizedShares * 0.40) * 100) / 100;
}

function getReadNewsIds(db, { userId, anonymousId } = {}) {
  return new Set(AnalyticsService.matchingInteractions(db, { userId, anonymousId })
    .filter((item) => ["view", "click", "read", "search_click", "recommendation_click", "save", "share"].includes(item.interaction_type))
    .map((item) => String(item.news_id || ""))
    .filter(Boolean));
}

function articleMatchesCategory(article = {}, category = "") {
  if (!category) return true;
  const wanted = VectorService.normalizeTurkishAscii(category);
  const labels = [article.category, article.subcategory, ...asArray(article.labels), ...asArray(article.tags), ...asArray(article.topics)]
    .filter(Boolean).map((item) => VectorService.normalizeTurkishAscii(item));
  return labels.includes(wanted);
}

function getDismissedNewsIds(db, { userId, anonymousId } = {}) {
  return new Set((db.userRecommendations || [])
    .filter((item) => {
      const sameUser = userId && String(item.user_id || "") === String(userId);
      const sameAnon = anonymousId && String(item.anonymous_id || "") === String(anonymousId);
      return (sameUser || sameAnon) && ["dismissed", "hidden"].includes(String(item.status || ""));
    })
    .map((item) => String(item.news_id || ""))
    .filter(Boolean));
}

function articlePool(db, { category = "" } = {}) {
  return (db.articles || [])
    .filter((article) => VectorService.getArticleId(article))
    .filter((article) => articleMatchesCategory(article, category));
}

function excludeReadArticles(candidates = [], readIds = new Set(), limit = DEFAULT_LIMIT) {
  if (!readIds || !readIds.size) return candidates;
  const filtered = candidates.filter((article) => !readIds.has(String(VectorService.getArticleId(article))));
  if (!filtered.length && candidates.length) {
    console.warn("[recommendations] Tüm öneriler okundu diye elendi; adaylar güvenli fallback olarak korunuyor.");
    return candidates.slice(0, Math.max(limit, DEFAULT_LIMIT));
  }
  return filtered;
}

function candidateArticles(db, { userId, anonymousId, excludeRead = true, category = "", limit = DEFAULT_LIMIT } = {}) {
  const base = articlePool(db, { category });
  const dismissedIds = getDismissedNewsIds(db, { userId, anonymousId });
  const withoutDismissed = dismissedIds.size
    ? base.filter((article) => !dismissedIds.has(String(VectorService.getArticleId(article))))
    : base;
  const safeBase = withoutDismissed.length ? withoutDismissed : base;
  const readIds = excludeRead ? getReadNewsIds(db, { userId, anonymousId }) : new Set();
  return excludeReadArticles(safeBase, readIds, limit);
}

function interactionScore(interaction = {}) {
  return Math.max(0, AnalyticsService.getInteractionWeight(interaction) * AnalyticsService.decayFactor(interaction.created_at));
}

function buildUserProfileVector(db, model, { userId, anonymousId } = {}) {
  const interactions = AnalyticsService.matchingInteractions(db, { userId, anonymousId })
    .filter((item) => item.news_id && ["view", "click", "read", "save", "share", "search_click", "recommendation_click"].includes(item.interaction_type));
  const vector = {};
  let weightSum = 0;
  for (const interaction of interactions) {
    const articleId = String(interaction.news_id);
    const articleVector = model.vectors.get(articleId);
    const weight = interactionScore(interaction);
    if (articleVector && weight > 0) {
      VectorService.addWeightedVector(vector, articleVector, weight);
      weightSum += weight;
    }
  }
  return { vector: weightSum > 0 ? VectorService.divideVector(vector, weightSum) : {}, weightSum, interactionCount: interactions.length };
}

function collaborativeScores(db, { userId, anonymousId } = {}) {
  const interactions = db.userInteractions || [];
  const currentKey = userId ? `u:${userId}` : `a:${anonymousId || "anon_demo"}`;
  const userItem = new Map();
  for (const item of interactions) {
    if (!item.news_id) continue;
    const key = item.user_id ? `u:${item.user_id}` : `a:${item.anonymous_id || "anon_demo"}`;
    const row = userItem.get(key) || {};
    row[String(item.news_id)] = (row[String(item.news_id)] || 0) + interactionScore(item);
    userItem.set(key, row);
  }
  const current = userItem.get(currentKey) || {};
  if (Object.keys(current).length < 3 || userItem.size < 2) return new Map();
  const similarities = [];
  for (const [key, row] of userItem.entries()) {
    if (key === currentKey) continue;
    const sim = VectorService.cosineSimilarity(current, row);
    if (sim > 0) similarities.push({ key, row, sim });
  }
  similarities.sort((a, b) => b.sim - a.sim);
  const scores = new Map();
  const readIds = new Set(Object.keys(current));
  for (const neighbor of similarities.slice(0, 10)) {
    for (const [newsId, value] of Object.entries(neighbor.row)) {
      if (readIds.has(newsId)) continue;
      scores.set(newsId, (scores.get(newsId) || 0) + neighbor.sim * value);
    }
  }
  const max = Math.max(0, ...scores.values());
  if (max > 0) {
    for (const [newsId, score] of scores.entries()) scores.set(newsId, Math.round((score / max) * 10000) / 100);
  }
  return scores;
}

function buildRecommendationReason(article = {}, profile = {}, contentScore = 0, collaborativeScore = 0) {
  const categories = profile.favorite_categories_json || {};
  const sources = profile.favorite_sources_json || {};
  const tags = profile.favorite_tags_json || {};
  const articleLabels = [article.category, ...asArray(article.labels), ...asArray(article.tags)].filter(Boolean);
  const matchedCategory = articleLabels.find((label) => categories[label] > 0);
  if (matchedCategory) return `${matchedCategory} haberlerini sık okuduğunuz için önerildi.`;
  const matchedTag = articleLabels.find((label) => tags[label] > 0);
  if (matchedTag) return `Daha önce ${matchedTag} konusuna benzer içeriklerle ilgilendiğiniz için önerildi.`;
  const source = VectorService.getArticleSourceName(article);
  if (source && sources[source] > 0) return `${source} kaynağındaki haberlerle ilgilendiğiniz için önerildi.`;
  if (collaborativeScore >= 55) return "Benzer kullanıcılar bu haberi okuduğu için önerildi.";
  if (contentScore >= 50) return "Okuduğunuz haberlere benzer olduğu için önerildi.";
  return "İlgi alanlarınıza uygun olabileceği için önerildi.";
}

function decorateRecommendationArticle(article = {}, scores = {}) {
  const idValue = VectorService.getArticleId(article) || article.news_id || article.id || `rec_article_${Date.now().toString(36)}`;
  const imageUrl = article.image_url || article.imageUrl || article.urlToImage || article.image || "/assets/news-placeholder.jpg";
  const sources = Array.isArray(article.sources) ? article.sources : [];
  const sourceName = article.source_name || article.sourceName || article.source || VectorService.getArticleSourceName(article) || "Kaynak belirtilmedi";
  const publishedAt = article.published_at || article.publishedAt || article.date || article.created_at || VectorService.getArticlePublishedAt(article) || null;
  const sourceCount = Number(article.source_count || article.sourceCount || sources.length || 1);
  return {
    ...article,
    id: idValue,
    news_id: idValue,
    cluster_id: article.cluster_id || article.clusterId || idValue,
    clusterId: article.clusterId || article.cluster_id || idValue,
    title: article.title || article.displayTitle || article.originalTitle || "Başlık bulunamadı",
    summary: article.summary || article.description || article.displaySummary || article.originalSummary || article.fullText?.slice?.(0, 180) || "Bu haber için özet bulunamadı.",
    category: article.category || "Genel",
    labels: Array.isArray(article.labels) ? article.labels : [],
    source_name: sourceName,
    sourceName,
    sources,
    source_count: sourceCount,
    sourceCount,
    published_at: publishedAt,
    publishedAt,
    image_url: imageUrl,
    imageUrl,
    url: article.url || article.sourceUrl || article.link || "#",
    recommendation_score: toNumber(scores.recommendation_score, 0),
    content_based_score: scores.content_based_score ?? null,
    collaborative_score: scores.collaborative_score ?? null,
    content_similarity_score: scores.content_similarity_score ?? 0,
    popularity_score: scores.popularity_score ?? 0,
    freshness_score: scores.freshness_score ?? 0,
    reason: scores.reason || "İlgi alanlarınıza uygun olabileceği için önerildi."
  };
}

function sortByRecommendation(a, b) {
  return (b.recommendation_score || 0) - (a.recommendation_score || 0)
    || new Date(b.published_at || b.publishedAt || 0) - new Date(a.published_at || a.publishedAt || 0);
}

function buildResponse({ data = [], source = "fallback", algorithm = source, message = "Öneriler başarıyla getirildi." } = {}) {
  return {
    success: true,
    source,
    algorithm,
    count: data.length,
    data,
    message: data.length ? message : "Şu anda önerilecek haber bulunamadı."
  };
}

function getPrecomputedRecommendations(db, { userId, anonymousId, limit = DEFAULT_LIMIT, category = "", excludeRead = true } = {}) {
  normalizeDb(db);
  const readIds = excludeRead ? getReadNewsIds(db, { userId, anonymousId }) : new Set();
  const dismissedIds = getDismissedNewsIds(db, { userId, anonymousId });
  const rows = (db.userRecommendations || [])
    .filter((item) => {
      const sameUser = userId && String(item.user_id || "") === String(userId);
      const sameAnon = anonymousId && String(item.anonymous_id || "") === String(anonymousId);
      return sameUser || sameAnon;
    })
    .filter((item) => !["dismissed", "hidden"].includes(String(item.status || "")))
    .filter((item) => item.news_id && !dismissedIds.has(String(item.news_id)))
    .filter((item) => !readIds.has(String(item.news_id)))
    .sort((a, b) => toNumber(b.recommendation_score, 0) - toNumber(a.recommendation_score, 0));
  const articles = [];
  const seen = new Set();
  for (const row of rows) {
    if (seen.has(String(row.news_id))) continue;
    const article = AnalyticsService.findArticle(db, row.news_id);
    if (!article || !articleMatchesCategory(article, category)) continue;
    seen.add(String(row.news_id));
    articles.push(decorateRecommendationArticle(article, {
      recommendation_score: row.recommendation_score || 0,
      content_based_score: row.content_based_score ?? null,
      collaborative_score: row.collaborative_score ?? null,
      content_similarity_score: row.content_similarity_score ?? 0,
      popularity_score: row.popularity_score ?? 0,
      freshness_score: row.freshness_score ?? calculateFreshnessScore(article),
      reason: row.reason || "Daha önceki ilgi alanlarınıza göre önerildi."
    }));
    if (articles.length >= limit) break;
  }
  return articles;
}

function computeContentBased(db, options = {}) {
  normalizeDb(db);
  const userId = options.userId || "user_demo";
  const anonymousId = options.anonymousId || "anon_demo";
  const limit = clamp(options.limit || DEFAULT_LIMIT, 1, MAX_LIMIT);
  const category = options.category || "";
  const excludeRead = options.excludeRead !== false;
  const candidates = candidateArticles(db, { userId, anonymousId, excludeRead, category, limit });
  const maxView = Math.max(0, ...(db.articles || []).map((a) => toNumber(a.view_count || a.viewCount, 0)));
  const maxShare = Math.max(0, ...(db.articles || []).map((a) => toNumber(a.share_count || a.shareCount, 0)));
  const model = VectorService.buildTfidfModel(db.articles || []);
  const profileVector = buildUserProfileVector(db, model, { userId, anonymousId });
  const profile = AnalyticsService.getProfile(db, { userId, anonymousId });
  const weakProfile = profileVector.interactionCount < 3 || !Object.keys(profileVector.vector).length;
  const results = candidates.map((article) => {
    const id = VectorService.getArticleId(article);
    const articleVector = model.vectors.get(id) || {};
    const similarity = Object.keys(profileVector.vector).length ? VectorService.cosineSimilarity(profileVector.vector, articleVector) * 100 : 0;
    const freshness = calculateFreshnessScore(article);
    const popularity = calculatePopularityScore(article, maxView, maxShare);
    const final = weakProfile
      ? (similarity * 0.50 + freshness * 0.25 + popularity * 0.25)
      : (similarity * 0.75 + freshness * 0.15 + popularity * 0.10);
    return decorateRecommendationArticle(article, {
      recommendation_score: Math.round(final * 100) / 100,
      content_based_score: Math.round(final * 100) / 100,
      collaborative_score: null,
      content_similarity_score: Math.round(similarity * 100) / 100,
      popularity_score: popularity,
      freshness_score: freshness,
      reason: buildRecommendationReason(article, profile, similarity, 0)
    });
  }).sort(sortByRecommendation).slice(0, limit);
  return buildResponse({
    data: results,
    source: weakProfile ? "category_popular_recent_fallback" : "content_based",
    algorithm: weakProfile ? "content_fallback_popular_recent" : "tfidf_cosine_content_based"
  });
}

function computeHybrid(db, options = {}) {
  normalizeDb(db);
  const userId = options.userId || "user_demo";
  const anonymousId = options.anonymousId || "anon_demo";
  const limit = clamp(options.limit || DEFAULT_LIMIT, 1, MAX_LIMIT);
  const category = options.category || "";
  const excludeRead = options.excludeRead !== false;
  const precomputed = getPrecomputedRecommendations(db, { userId, anonymousId, limit, category, excludeRead });
  if (precomputed.length) {
    return buildResponse({ data: precomputed, source: "precomputed", algorithm: "precomputed_user_recommendations" });
  }
  const candidates = candidateArticles(db, { userId, anonymousId, excludeRead, category, limit });
  const maxView = Math.max(0, ...(db.articles || []).map((a) => toNumber(a.view_count || a.viewCount, 0)));
  const maxShare = Math.max(0, ...(db.articles || []).map((a) => toNumber(a.share_count || a.shareCount, 0)));
  const model = VectorService.buildTfidfModel(db.articles || []);
  const profileVector = buildUserProfileVector(db, model, { userId, anonymousId });
  const profile = AnalyticsService.getProfile(db, { userId, anonymousId });
  const collabMap = collaborativeScores(db, { userId, anonymousId });
  const noInteractions = profileVector.interactionCount === 0;
  const results = candidates.map((article) => {
    const id = VectorService.getArticleId(article);
    const similarity = Object.keys(profileVector.vector).length ? VectorService.cosineSimilarity(profileVector.vector, model.vectors.get(id) || {}) * 100 : 0;
    const freshness = calculateFreshnessScore(article);
    const popularity = calculatePopularityScore(article, maxView, maxShare);
    const collaborative = collabMap.has(id) ? collabMap.get(id) : null;
    let score;
    if (noInteractions) score = popularity * 0.50 + freshness * 0.30 + (article.category ? 20 : 0) * 0.20;
    else if (collaborative === null) score = similarity * 0.70 + popularity * 0.15 + freshness * 0.15;
    else score = similarity * 0.45 + collaborative * 0.35 + popularity * 0.10 + freshness * 0.10;
    return decorateRecommendationArticle(article, {
      recommendation_score: Math.round(score * 100) / 100,
      content_based_score: Math.round((similarity * 0.70 + popularity * 0.15 + freshness * 0.15) * 100) / 100,
      collaborative_score: collaborative,
      content_similarity_score: Math.round(similarity * 100) / 100,
      popularity_score: popularity,
      freshness_score: freshness,
      reason: noInteractions ? "Yeni başladığınız için trend ve güncel haberlerden önerildi." : buildRecommendationReason(article, profile, similarity, collaborative || 0)
    });
  }).sort(sortByRecommendation).slice(0, limit);
  saveRecommendations(db, userId, results);
  return buildResponse({
    data: results,
    source: noInteractions ? "trend_popular_recent_fallback" : "hybrid",
    algorithm: noInteractions ? "cold_start_trending_recent" : (collabMap.size ? "hybrid_content_collaborative" : "hybrid_content_fallback")
  });
}

function saveRecommendations(db, userId, recommendations = []) {
  normalizeDb(db);
  const now = nowIso();
  for (const rec of recommendations) {
    const existing = db.userRecommendations.find((item) => String(item.user_id) === String(userId) && String(item.news_id) === String(rec.news_id));
    const payload = {
      user_id: userId,
      news_id: rec.news_id,
      recommendation_score: rec.recommendation_score,
      content_based_score: rec.content_based_score,
      collaborative_score: rec.collaborative_score,
      content_similarity_score: rec.content_similarity_score,
      popularity_score: rec.popularity_score,
      freshness_score: rec.freshness_score,
      reason: rec.reason,
      status: existing?.status && ["clicked", "dismissed"].includes(existing.status) ? existing.status : "active",
      updated_at: now
    };
    if (existing) Object.assign(existing, payload);
    else db.userRecommendations.push({ id: `rec_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 8)}`, created_at: now, ...payload });
  }
}

function applyFeedback(db, { userId = "user_demo", anonymousId = "anon_demo", newsId, feedback } = {}) {
  normalizeDb(db);
  const allowed = new Set(["interested", "not_interested", "show_less", "show_more_from_source", "hide_source"]);
  if (!allowed.has(feedback)) {
    const error = new Error("Geçersiz öneri feedback değeri.");
    error.statusCode = 422;
    throw error;
  }
  const article = AnalyticsService.findArticle(db, newsId);
  let rec = db.userRecommendations.find((item) => String(item.user_id || "") === String(userId || "") && String(item.news_id) === String(newsId));
  const feedbackStatus = feedback === "not_interested" || feedback === "show_less" || feedback === "hide_source" ? "dismissed" : "clicked";
  if (!rec && newsId) {
    rec = {
      id: `recfb_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 8)}`,
      user_id: userId || null,
      anonymous_id: anonymousId || null,
      news_id: String(newsId),
      recommendation_score: 0,
      reason: "Kullanıcı geri bildirimi ile kaydedildi.",
      created_at: nowIso()
    };
    db.userRecommendations.push(rec);
  }
  if (rec) {
    rec.status = feedbackStatus;
    rec.feedback = feedback;
    rec.updated_at = nowIso();
  }
  AnalyticsService.trackInteraction(db, {
    news_id: newsId,
    interaction_type: feedback === "interested" || feedback === "show_more_from_source" ? "recommendation_click" : "recommendation_impression",
    metadata: { recommendation_feedback: feedback, source: "recommendations" }
  }, { userId, anonymousId });
  if (article && feedback === "hide_source") {
    const profile = AnalyticsService.getProfile(db, { userId, anonymousId });
    const source = VectorService.getArticleSourceName(article);
    profile.favorite_sources_json = profile.favorite_sources_json || {};
    profile.favorite_sources_json[source] = Math.min(-20, Number(profile.favorite_sources_json[source] || 0) - 20);
  }
  return { success: true, news_id: newsId, feedback, status: rec?.status || "recorded" };
}

function recomputeAll(db, { maxUsers = 250 } = {}) {
  normalizeDb(db);
  const users = new Set();
  for (const interaction of db.userInteractions) {
    if (interaction.user_id) users.add(String(interaction.user_id));
  }
  users.add("user_demo");
  let count = 0;
  for (const userId of [...users].slice(0, maxUsers)) {
    AnalyticsService.updateUserProfile(db, { userId, anonymousId: "anon_demo" });
    computeHybrid(db, { userId, anonymousId: "anon_demo", limit: 20 });
    count += 1;
  }
  return { success: true, users: count, generatedAt: nowIso() };
}

module.exports = {
  normalizeDb,
  calculateFreshnessScore,
  calculatePopularityScore,
  getReadNewsIds,
  collaborativeScores,
  computeContentBased,
  computeHybrid,
  applyFeedback,
  saveRecommendations,
  getPrecomputedRecommendations,
  excludeReadArticles,
  recomputeAll,
  buildRecommendationReason
};
