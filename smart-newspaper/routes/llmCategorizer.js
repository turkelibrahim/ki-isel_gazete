"use strict";

const {
  LLM_CATEGORIZER_CONFIG,
  categorizeArticle,
  categorizeArticles,
  parseAndValidateResponse,
  validateLLMOutput,
  getAdminQueue,
  getUsageStats,
  buildLLMCategorizerStats
} = require("../services/llmCategorizerService");

async function handleLLMCategorizerRoute(req, res, url, helpers) {
  if (!url.pathname.startsWith("/api/llm-categorizer") && !url.pathname.startsWith("/api/llmCategorizer")) return false;
  const { readBody, json } = helpers;

  if (req.method === "GET" && (url.pathname === "/api/llm-categorizer/config" || url.pathname === "/api/llmCategorizer/config")) {
    return json(res, 200, {
      success: true,
      ...LLM_CATEGORIZER_CONFIG,
      enabled: String(process.env.LLM_CATEGORIZER_ENABLED || "true").toLowerCase() !== "false",
      hasClaudeKey: Boolean(process.env.ANTHROPIC_API_KEY),
      hasOpenAIKey: Boolean(process.env.OPENAI_API_KEY)
    });
  }

  if (req.method === "POST" && (url.pathname === "/api/llm-categorizer/classify" || url.pathname === "/api/llmCategorizer/classify")) {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : null;
      if (articles) {
        const results = await categorizeArticles(articles, body.options || body);
        return json(res, 200, {
          success: true,
          results,
          data: { results },
          llmCategorizerStats: buildLLMCategorizerStats(articles.map((article, index) => ({ ...article, llm_validation: results[index] })))
        });
      }
      const article = body.article || body;
      const result = await categorizeArticle(article, body.options || body);
      return json(res, 200, { success: true, result, llm_validation: result, data: { result } });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: {
          code: "LLM_CATEGORIZATION_FAILED",
          message: "LLM doğrulaması geçici olarak çalışmadı; haber akışı korunmalı.",
          detail: error.message
        },
        result: null
      });
    }
  }

  if (req.method === "POST" && (url.pathname === "/api/llm-categorizer/batch" || url.pathname === "/api/llmCategorizer/batch")) {
    try {
      const body = await readBody(req);
      const articles = Array.isArray(body.articles) ? body.articles : [];
      const results = await categorizeArticles(articles, body.options || body);
      return json(res, 200, { success: true, results, data: { results } });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: { code: "LLM_BATCH_FAILED", message: "Batch doğrulama geçici olarak çalışmadı.", detail: error.message },
        results: []
      });
    }
  }

  if (req.method === "POST" && (url.pathname === "/api/llm-categorizer/validate" || url.pathname === "/api/llmCategorizer/validate")) {
    try {
      const body = await readBody(req);
      const raw = body.raw_response || body.rawResponse;
      const validation = raw ? parseAndValidateResponse(raw) : validateLLMOutput(body.output || body);
      return json(res, 200, { success: validation.valid, validation });
    } catch (error) {
      return json(res, 200, {
        success: false,
        error: { code: "LLM_VALIDATION_FAILED", message: "LLM yanıt doğrulaması çalışmadı.", detail: error.message }
      });
    }
  }

  if (req.method === "GET" && (url.pathname === "/api/llm-categorizer/usage" || url.pathname === "/api/llmCategorizer/usage")) {
    return json(res, 200, { success: true, usage: getUsageStats() });
  }

  if (req.method === "GET" && (url.pathname === "/api/llm-categorizer/admin-queue" || url.pathname === "/api/llmCategorizer/admin-queue")) {
    return json(res, 200, { success: true, queue: getAdminQueue(), count: getAdminQueue().length });
  }

  return false;
}

module.exports = { handleLLMCategorizerRoute };
