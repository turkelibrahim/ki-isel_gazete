"use strict";

const AnalyticsService = require("../services/analyticsService");

async function handleAnalyticsRoute(req, res, url, context = {}) {
  const { readBody, json, db, writeDb, getUserId = () => "user_demo" } = context;
  if (!url.pathname.startsWith("/api/analytics")) return false;
  AnalyticsService.normalizeDb(db);
  const userId = getUserId(req);
  const anonymousId = req.headers["x-anonymous-id"] || url.searchParams.get("anonymousId") || "anon_demo";

  if (req.method === "POST" && url.pathname === "/api/analytics/track") {
    try {
      const body = await readBody(req);
      const result = AnalyticsService.trackInteraction(db, body, { userId, anonymousId, req });
      writeDb?.(db);
      return json(res, 201, result);
    } catch (error) {
      return json(res, error.statusCode || 400, { success: false, message: error.message || "Etkileşim kaydedilemedi." });
    }
  }

  if (req.method === "GET" && url.pathname === "/api/analytics/dashboard") {
    const payload = AnalyticsService.buildDashboard(db, { userId, anonymousId });
    return json(res, 200, payload);
  }

  return false;
}

module.exports = { handleAnalyticsRoute };
