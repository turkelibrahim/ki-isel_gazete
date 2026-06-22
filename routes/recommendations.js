"use strict";

const RecommendationService = require("../services/recommendationService");

function queryOptions(url, req, getUserId) {
  return {
    userId: getUserId(req),
    anonymousId: req.headers["x-anonymous-id"] || url.searchParams.get("anonymousId") || "anon_demo",
    limit: Number(url.searchParams.get("limit") || 12),
    category: url.searchParams.get("category") || "",
    excludeRead: url.searchParams.get("excludeRead") !== "false"
  };
}

async function handleRecommendationsRoute(req, res, url, context = {}) {
  const { readBody, json, db, writeDb, getUserId = () => "user_demo" } = context;
  if (!url.pathname.startsWith("/api/recommendations")) return false;
  RecommendationService.normalizeDb(db);

  if (req.method === "GET" && url.pathname === "/api/recommendations") {
    try {
      const payload = RecommendationService.computeHybrid(db, queryOptions(url, req, getUserId));
      writeDb?.(db);
      return json(res, 200, payload);
    } catch (error) {
      console.error("[recommendations] hybrid endpoint failed:", error);
      return json(res, 200, {
        success: true,
        source: "safe_fallback",
        algorithm: "safe_fallback",
        count: 0,
        data: [],
        message: "Öneriler yüklenirken sorun oluştu; ana akış etkilenmeden devam ediyor."
      });
    }
  }

  if (req.method === "GET" && url.pathname === "/api/recommendations/content-based") {
    try {
      const payload = RecommendationService.computeContentBased(db, queryOptions(url, req, getUserId));
      writeDb?.(db);
      return json(res, 200, payload);
    } catch (error) {
      console.error("[recommendations] content endpoint failed:", error);
      return json(res, 200, {
        success: true,
        source: "safe_fallback",
        algorithm: "safe_fallback",
        count: 0,
        data: [],
        message: "İçerik tabanlı öneriler alınamadı; güvenli boş yanıt döndürüldü."
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/api/recommendations/feedback") {
    try {
      const body = await readBody(req);
      const payload = RecommendationService.applyFeedback(db, {
        userId: getUserId(req),
        anonymousId: req.headers["x-anonymous-id"] || body.anonymous_id || body.anonymousId || "anon_demo",
        newsId: body.news_id || body.newsId || body.article_id || body.articleId,
        feedback: body.feedback
      });
      writeDb?.(db);
      return json(res, 200, payload);
    } catch (error) {
      return json(res, error.statusCode || 400, { success: false, message: error.message || "Öneri feedback kaydedilemedi." });
    }
  }

  return false;
}

module.exports = { handleRecommendationsRoute };
