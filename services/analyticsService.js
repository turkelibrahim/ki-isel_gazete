"use strict";

const crypto = require("crypto");
const VectorService = require("./vectorService");

const INTERACTION_TYPES = new Set([
  "view", "click", "read", "save", "unsave", "share", "category_click", "source_click", "search_click", "recommendation_impression", "recommendation_click"
]);

const INTERACTION_WEIGHTS = Object.freeze({
  view: 1,
  click: 2,
  read: 3,
  save: 6,
  unsave: -3,
  share: 5,
  category_click: 1.5,
  source_click: 1.5,
  search_click: 3,
  recommendation_impression: 0.25,
  recommendation_click: 5
});

function nowIso() { return new Date().toISOString(); }
function toNumber(value, fallback = 0) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function clamp(n, min, max) { return Math.min(max, Math.max(min, toNumber(n, min))); }
function id(prefix) { return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(5).toString("hex")}`; }
function hashValue(value = "") { return crypto.createHash("sha256").update(String(value || "")).digest("hex"); }
function todayKey(date = new Date()) { return date.toISOString().slice(0, 10); }

function normalizeDb(db = {}) {
  db.userSessions = Array.isArray(db.userSessions) ? db.userSessions : [];
  db.userInteractions = Array.isArray(db.userInteractions) ? db.userInteractions : [];
  db.userProfiles = Array.isArray(db.userProfiles) ? db.userProfiles : [];
  db.newsVectors = Array.isArray(db.newsVectors) ? db.newsVectors : [];
  db.userRecommendations = Array.isArray(db.userRecommendations) ? db.userRecommendations : [];
  db.analyticsLogs = Array.isArray(db.analyticsLogs) ? db.analyticsLogs : [];
  return db;
}

function getClientIp(req) {
  const forwarded = req?.headers?.["x-forwarded-for"] || "";
  return String(forwarded).split(",")[0].trim() || req?.socket?.remoteAddress || "";
}

function getOrCreateSession(db, { userId = "user_demo", anonymousId = "anon_demo", sessionId = "", req } = {}) {
  normalizeDb(db);
  const sid = String(sessionId || req?.headers?.["x-session-id"] || id("sess"));
  let session = db.userSessions.find((item) => String(item.session_id) === sid);
  if (!session) {
    const ua = req?.headers?.["user-agent"] || "";
    session = {
      id: id("session"),
      user_id: userId || null,
      anonymous_id: anonymousId || null,
      session_id: sid,
      started_at: nowIso(),
      ended_at: null,
      device_type: /mobile|android|iphone/i.test(ua) ? "mobile" : "desktop",
      browser: String(ua).slice(0, 120),
      ip_hash: getClientIp(req) ? hashValue(getClientIp(req)) : "",
      user_agent: String(ua).slice(0, 500),
      created_at: nowIso()
    };
    db.userSessions.push(session);
  } else {
    session.user_id = userId || session.user_id || null;
    session.anonymous_id = anonymousId || session.anonymous_id || null;
  }
  return session;
}

function findArticle(db, newsId) {
  const idValue = String(newsId || "");
  return (db.articles || []).find((article) => String(VectorService.getArticleId(article)) === idValue) || null;
}

function getInteractionWeight(interaction = {}) {
  let weight = INTERACTION_WEIGHTS[interaction.interaction_type] ?? 1;
  const duration = clamp(interaction.duration_seconds || 0, 0, 600);
  if (interaction.interaction_type === "read") {
    if (duration < 5) weight = Math.max(0.5, weight - 2);
    if (duration >= 30) weight += 2;
    if (duration >= 60) weight += 3;
    if (duration >= 180) weight += 4;
  }
  return weight;
}

function decayFactor(createdAt, now = new Date()) {
  const date = new Date(createdAt || now);
  if (Number.isNaN(date.getTime())) return 1;
  const daysOld = Math.max(0, (now.getTime() - date.getTime()) / 86400000);
  return 1 / (1 + daysOld * 0.05);
}

function emptyProfile({ userId, anonymousId }) {
  return {
    id: id("profile"),
    user_id: userId || null,
    anonymous_id: anonymousId || null,
    favorite_categories_json: {},
    favorite_sources_json: {},
    favorite_tags_json: {},
    average_reading_time: 0,
    total_reading_time: 0,
    total_articles_read: 0,
    last_active_at: nowIso(),
    profile_vector_json: {},
    updated_at: nowIso()
  };
}

function getProfile(db, { userId, anonymousId }) {
  normalizeDb(db);
  let profile = db.userProfiles.find((item) => String(item.user_id || "") === String(userId || "") && String(item.anonymous_id || "") === String(anonymousId || ""));
  if (!profile && userId) profile = db.userProfiles.find((item) => String(item.user_id || "") === String(userId));
  if (!profile && anonymousId) profile = db.userProfiles.find((item) => String(item.anonymous_id || "") === String(anonymousId));
  if (!profile) {
    profile = emptyProfile({ userId, anonymousId });
    db.userProfiles.push(profile);
  }
  return profile;
}

function addScore(map, key, amount) {
  const k = String(key || "").trim();
  if (!k) return;
  map[k] = Math.round(((map[k] || 0) + amount) * 100) / 100;
}

function matchingInteractions(db, { userId, anonymousId } = {}) {
  normalizeDb(db);
  return db.userInteractions.filter((item) => {
    if (userId && String(item.user_id || "") === String(userId)) return true;
    if (anonymousId && String(item.anonymous_id || "") === String(anonymousId)) return true;
    return false;
  });
}

function updateUserProfile(db, { userId, anonymousId } = {}) {
  normalizeDb(db);
  const profile = getProfile(db, { userId, anonymousId });
  const interactions = matchingInteractions(db, { userId, anonymousId });
  const categoryScores = {};
  const sourceScores = {};
  const tagScores = {};
  let readDuration = 0;
  let readEvents = 0;
  const readIds = new Set();
  const model = VectorService.buildTfidfModel(db.articles || []);
  const profileVector = {};
  let vectorWeightSum = 0;

  for (const interaction of interactions) {
    const article = findArticle(db, interaction.news_id);
    const baseWeight = getInteractionWeight(interaction);
    const finalWeight = baseWeight * decayFactor(interaction.created_at);
    if (interaction.category) addScore(categoryScores, interaction.category, finalWeight);
    if (interaction.source_name) addScore(sourceScores, interaction.source_name, finalWeight);
    if (article) {
      addScore(categoryScores, article.category, finalWeight);
      addScore(sourceScores, VectorService.getArticleSourceName(article), finalWeight);
      for (const tag of VectorService.getArticleLabels(article)) addScore(tagScores, tag, finalWeight);
      const vector = model.vectors.get(VectorService.getArticleId(article));
      if (vector && finalWeight > 0) {
        VectorService.addWeightedVector(profileVector, vector, finalWeight);
        vectorWeightSum += finalWeight;
      }
    }
    if (["read", "view", "click", "search_click", "recommendation_click"].includes(interaction.interaction_type) && interaction.news_id) readIds.add(String(interaction.news_id));
    if (interaction.interaction_type === "read") {
      readDuration += clamp(interaction.duration_seconds || 0, 0, 600);
      readEvents += 1;
    }
  }

  profile.favorite_categories_json = categoryScores;
  profile.favorite_sources_json = sourceScores;
  profile.favorite_tags_json = tagScores;
  profile.average_reading_time = readEvents ? Math.round(readDuration / readEvents) : 0;
  profile.total_reading_time = Math.round(readDuration);
  profile.total_articles_read = readIds.size;
  profile.last_active_at = interactions.length ? interactions.map((i) => i.created_at).sort().slice(-1)[0] : profile.last_active_at || nowIso();
  profile.profile_vector_json = vectorWeightSum > 0 ? VectorService.divideVector(profileVector, vectorWeightSum) : {};
  profile.updated_at = nowIso();
  return profile;
}

function validateInteractionPayload(payload = {}) {
  const type = String(payload.interaction_type || payload.type || "").trim();
  if (!INTERACTION_TYPES.has(type)) {
    const allowed = [...INTERACTION_TYPES].join(", ");
    const error = new Error(`Geçersiz interaction_type. İzin verilenler: ${allowed}`);
    error.statusCode = 422;
    throw error;
  }
  const duration = clamp(payload.duration_seconds || payload.durationSeconds || 0, 0, 600);
  return {
    news_id: payload.news_id ?? payload.newsId ?? payload.article_id ?? payload.articleId ?? null,
    interaction_type: type,
    duration_seconds: duration,
    metadata: payload.metadata && typeof payload.metadata === "object" ? payload.metadata : {},
    session_id: String(payload.session_id || payload.sessionId || ""),
    anonymous_id: String(payload.anonymous_id || payload.anonymousId || "anon_demo")
  };
}

function trackInteraction(db, payload = {}, { userId = "user_demo", anonymousId = "anon_demo", req } = {}) {
  normalizeDb(db);
  const valid = validateInteractionPayload(payload);
  const session = getOrCreateSession(db, { userId, anonymousId: valid.anonymous_id || anonymousId, sessionId: valid.session_id, req });
  const article = valid.news_id ? findArticle(db, valid.news_id) : null;
  const category = valid.metadata.category || article?.category || "";
  const sourceName = valid.metadata.source_name || valid.metadata.sourceName || (article ? VectorService.getArticleSourceName(article) : "");
  const interaction = {
    id: id("interaction"),
    user_id: userId || null,
    anonymous_id: valid.anonymous_id || anonymousId || null,
    session_id: session.session_id,
    news_id: valid.news_id ? String(valid.news_id) : null,
    category,
    source_name: sourceName,
    interaction_type: valid.interaction_type,
    duration_seconds: valid.duration_seconds,
    metadata_json: valid.metadata,
    created_at: nowIso()
  };
  db.userInteractions.push(interaction);

  if (article) {
    if (["view", "click", "read"].includes(valid.interaction_type)) {
      article.view_count = toNumber(article.view_count || article.viewCount, 0) + 1;
      article.viewCount = article.view_count;
    }
    if (valid.interaction_type === "share") {
      article.share_count = toNumber(article.share_count || article.shareCount, 0) + 1;
      article.shareCount = article.share_count;
    }
    if (valid.interaction_type === "search_click") {
      article.search_click_count = toNumber(article.search_click_count || article.searchClickCount, 0) + 1;
      article.searchClickCount = article.search_click_count;
    }
  }

  if (valid.interaction_type === "recommendation_click" && valid.news_id) {
    for (const rec of db.userRecommendations) {
      if (String(rec.news_id) === String(valid.news_id) && String(rec.user_id || "") === String(userId || "")) {
        rec.status = "clicked";
        rec.updated_at = nowIso();
      }
    }
  }
  if (valid.interaction_type === "recommendation_impression" && valid.news_id) {
    for (const rec of db.userRecommendations) {
      if (String(rec.news_id) === String(valid.news_id) && String(rec.user_id || "") === String(userId || "") && rec.status === "active") {
        rec.status = "shown";
        rec.updated_at = nowIso();
      }
    }
  }

  const profile = updateUserProfile(db, { userId, anonymousId: valid.anonymous_id || anonymousId });
  return { success: true, interaction, profile, article };
}

function buildDashboard(db, { userId = "user_demo", anonymousId = "anon_demo" } = {}) {
  normalizeDb(db);
  const interactions = matchingInteractions(db, { userId, anonymousId });
  const readLike = interactions.filter((item) => ["view", "click", "read", "search_click", "recommendation_click"].includes(item.interaction_type));
  const distinctRead = new Set(readLike.map((item) => item.news_id).filter(Boolean));
  const totalReadingTimeSeconds = interactions.filter((item) => item.interaction_type === "read").reduce((sum, item) => sum + clamp(item.duration_seconds || 0, 0, 600), 0);
  const since7 = Date.now() - 7 * 86400000;
  const weeklyReadingSeconds = interactions
    .filter((item) => item.interaction_type === "read" && new Date(item.created_at).getTime() >= since7)
    .reduce((sum, item) => sum + clamp(item.duration_seconds || 0, 0, 600), 0);
  const categoryMap = new Map();
  const sourceMap = new Map();
  const weeklyMap = new Map();
  const recent = [];
  for (const interaction of interactions) {
    const article = interaction.news_id ? findArticle(db, interaction.news_id) : null;
    const category = interaction.category || article?.category || "Bilinmiyor";
    const sourceName = interaction.source_name || (article ? VectorService.getArticleSourceName(article) : "Kaynak belirtilmedi");
    if (["view", "click", "read", "search_click", "recommendation_click"].includes(interaction.interaction_type)) {
      const cat = categoryMap.get(category) || { category, count: 0, reading_time_minutes: 0 };
      cat.count += 1;
      cat.reading_time_minutes += Math.round(clamp(interaction.duration_seconds || 0, 0, 600) / 60);
      categoryMap.set(category, cat);
      const src = sourceMap.get(sourceName) || { source_name: sourceName, count: 0 };
      src.count += 1;
      sourceMap.set(sourceName, src);
      if (article) recent.push({ id: VectorService.getArticleId(article), title: VectorService.getArticleTitle(article), category: article.category, source_name: VectorService.getArticleSourceName(article), created_at: interaction.created_at });
    }
    if (interaction.interaction_type === "read") {
      const day = todayKey(new Date(interaction.created_at));
      const row = weeklyMap.get(day) || { date: day, reading_time_minutes: 0, article_count: 0 };
      row.reading_time_minutes += Math.round(clamp(interaction.duration_seconds || 0, 0, 600) / 60);
      row.article_count += 1;
      weeklyMap.set(day, row);
    }
  }
  const savedArticlesCount = interactions.filter((item) => item.interaction_type === "save").length;
  const recommendationImpressions = interactions.filter((item) => item.interaction_type === "recommendation_impression").length;
  const recommendationClicks = interactions.filter((item) => item.interaction_type === "recommendation_click").length;
  return {
    success: true,
    summary: {
      total_articles_read: distinctRead.size,
      total_reading_time_minutes: Math.round(totalReadingTimeSeconds / 60),
      weekly_reading_time_minutes: Math.round(weeklyReadingSeconds / 60),
      saved_articles_count: savedArticlesCount,
      recommendation_ctr: recommendationImpressions ? Math.round((recommendationClicks / recommendationImpressions) * 10000) / 100 : 0
    },
    top_categories: [...categoryMap.values()].sort((a, b) => b.count - a.count).slice(0, 8),
    weekly_reading: [...weeklyMap.values()].sort((a, b) => a.date.localeCompare(b.date)),
    top_sources: [...sourceMap.values()].sort((a, b) => b.count - a.count).slice(0, 8),
    recent_articles: recent.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 10),
    empty: interactions.length === 0,
    message: interactions.length ? "" : "Henüz yeterli okuma veriniz yok. Haber okudukça istatistikleriniz burada görünecek."
  };
}

module.exports = {
  INTERACTION_TYPES,
  INTERACTION_WEIGHTS,
  normalizeDb,
  getOrCreateSession,
  getInteractionWeight,
  decayFactor,
  validateInteractionPayload,
  trackInteraction,
  updateUserProfile,
  getProfile,
  matchingInteractions,
  buildDashboard,
  findArticle,
  hashValue,
  nowIso
};
