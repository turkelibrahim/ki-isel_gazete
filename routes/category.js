"use strict";

const {
  CATEGORY_CONFIG,
  classifyArticle,
  classifyArticles,
  groupArticlesByCategory,
  buildCategoryStats,
  sortArticlesForPersonalNewspaper
} = require("../services/categoryService");

async function handleCategoryRoute(req, res, url, helpers) {
  if (!url.pathname.startsWith("/api/category")) return false;
  const { readBody, json } = helpers;

  if (req.method === "GET" && url.pathname === "/api/category/config") {
    return json(res, 200, {
      success: true,
      categories: CATEGORY_CONFIG.categories,
      sectionOrder: CATEGORY_CONFIG.sectionOrder,
      threshold: Number(process.env.CATEGORY_CONFIDENCE_THRESHOLD || 0.85),
      expandable: true
    });
  }

  if (req.method === "POST" && url.pathname === "/api/category/classify") {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : null;
      if (articles) {
        const enriched = classifyArticles(articles);
        return json(res, 200, {
          success: true,
          articles: enriched,
          data: { articles: enriched },
          categoryStats: buildCategoryStats(enriched)
        });
      }
      const prediction = classifyArticle(body.article || body);
      return json(res, 200, { success: true, prediction });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "CATEGORY_CLASSIFICATION_FAILED",
          message: "Kategori sınıflandırma geçici olarak çalışmadı; haber akışı korunmalı.",
          detail: error.message
        },
        articles: [],
        data: { articles: [] }
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/api/category/group") {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : [];
      const sorted = body.personalized
        ? sortArticlesForPersonalNewspaper(articles, body.preferences || {})
        : classifyArticles(articles);
      const groups = groupArticlesByCategory(sorted);
      return json(res, 200, {
        success: true,
        groups,
        categoryGroups: groups,
        categoryStats: buildCategoryStats(sorted)
      });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "CATEGORY_GROUPING_FAILED",
          message: "Kategori gruplaması geçici olarak çalışmadı.",
          detail: error.message
        },
        groups: {}
      });
    }
  }

  return false;
}

module.exports = { handleCategoryRoute };
