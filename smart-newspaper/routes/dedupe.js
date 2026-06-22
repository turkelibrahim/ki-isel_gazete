"use strict";

const { dedupeArticles, buildDedupeStats } = require("../services/dedupeService");

async function handleDedupeRoute(req, res, url, helpers) {
  if (!url.pathname.startsWith("/api/dedupe")) return false;
  const { readBody, json } = helpers;

  if (req.method === "POST" && url.pathname === "/api/dedupe/cluster") {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : [];
      const clusters = dedupeArticles(articles, { limit: Number(body.limit || articles.length || 120) });
      return json(res, 200, {
        success: true,
        mode: "clustered",
        articles: clusters,
        data: { articles: clusters },
        clusterStats: buildDedupeStats(clusters, articles.length)
      });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "DEDUPE_FAILED",
          message: "Haber gruplama geçici olarak çalışmadı; orijinal haber akışı korunmalı.",
          detail: error.message
        },
        articles: [],
        data: { articles: [] }
      });
    }
  }

  return false;
}

module.exports = { handleDedupeRoute };
