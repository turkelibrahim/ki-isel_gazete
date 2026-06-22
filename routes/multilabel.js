"use strict";

const {
  MULTILABEL_CONFIG,
  classifyArticleLabels,
  classifyArticlesLabels,
  groupArticlesByLabel,
  buildMultilabelStats,
  sortArticlesForPersonalLabels,
  validatePrediction
} = require("../services/multilabelService");

async function handleMultilabelRoute(req, res, url, helpers) {
  if (!url.pathname.startsWith("/api/multilabel")) return false;
  const { readBody, json } = helpers;

  if (req.method === "GET" && url.pathname === "/api/multilabel/config") {
    return json(res, 200, {
      success: true,
      ...MULTILABEL_CONFIG
    });
  }

  if (req.method === "POST" && url.pathname === "/api/multilabel/classify") {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : null;
      if (articles) {
        const enriched = classifyArticlesLabels(articles);
        return json(res, 200, {
          success: true,
          articles: enriched,
          data: { articles: enriched },
          multilabelStats: buildMultilabelStats(enriched)
        });
      }
      const prediction = classifyArticleLabels(body.article || body);
      return json(res, 200, { success: true, prediction });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "MULTILABEL_CLASSIFICATION_FAILED",
          message: "Çoklu etiketleme geçici olarak çalışmadı; haber akışı korunmalı.",
          detail: error.message
        },
        articles: [],
        data: { articles: [] }
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/api/multilabel/group") {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : [];
      const classified = body.personalized
        ? sortArticlesForPersonalLabels(articles, body.preferences || {})
        : classifyArticlesLabels(articles);
      const labelGroups = groupArticlesByLabel(classified);
      return json(res, 200, {
        success: true,
        labelGroups,
        groups: labelGroups,
        multilabelStats: buildMultilabelStats(classified)
      });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "MULTILABEL_GROUPING_FAILED",
          message: "Etiket gruplaması geçici olarak çalışmadı.",
          detail: error.message
        },
        labelGroups: {}
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/api/multilabel/validate") {
    try {
      const body = await readBody(req);
      return json(res, 200, { success: true, prediction: validatePrediction(body.prediction || body) });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "MULTILABEL_VALIDATION_FAILED",
          message: "Etiket doğrulaması çalışmadı.",
          detail: error.message
        }
      });
    }
  }

  return false;
}

module.exports = { handleMultilabelRoute };
