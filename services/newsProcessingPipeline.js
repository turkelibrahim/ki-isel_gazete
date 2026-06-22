"use strict";

const { applyCategoryToArticle } = require("./categoryService");
const { applyMultilabelToArticle } = require("./multilabelService");
const { applyLLMValidationToArticleSync } = require("./llmCategorizerService");

function processNewsArticle(article = {}, options = {}) {
  const output = article && typeof article === "object" ? { ...article } : {};
  try { applyCategoryToArticle(output, { preserveReliable: true }); } catch { /* keep feed safe */ }
  try { applyMultilabelToArticle(output, { preserveReliable: true }); } catch { /* keep feed safe */ }
  try { applyLLMValidationToArticleSync(output, options.llm || {}); } catch { /* keep feed safe */ }
  return output;
}

function processNewsBatch(articles = [], options = {}) {
  return (Array.isArray(articles) ? articles : []).map((article) => processNewsArticle(article, options));
}

module.exports = { processNewsArticle, processNewsBatch };
