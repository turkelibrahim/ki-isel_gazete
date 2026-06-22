
"use strict";

const { applyCorrectionToArticle, applyCorrectionToCluster, buildFeedCorrectionStats } = require("./adminReclassificationService");

function applyAdminCorrectionsToFeedArticles(articles = []) {
  return Array.isArray(articles) ? articles.map((article) => applyCorrectionToCluster(applyCorrectionToArticle(article))) : [];
}

module.exports = { applyAdminCorrectionsToFeedArticles, applyCorrectionToArticle, applyCorrectionToCluster, buildFeedCorrectionStats };
