"use strict";

const fs = require("fs");
const path = require("path");

const DB_PATHS = [
  path.join(__dirname, "..", "db", "data.json"),
  path.join(__dirname, "..", "db", "seed.json"),
  path.join(__dirname, "..", "db", "demo-regional-pandemic.json")
];

function migrateFile(filePath) {
  if (!fs.existsSync(filePath)) return { filePath, skipped: true };
  let data;
  try { data = JSON.parse(fs.readFileSync(filePath, "utf8")); }
  catch (error) { return { filePath, error: error.message }; }
  if (!data || typeof data !== "object" || Array.isArray(data)) return { filePath, skipped: true };
  let changed = false;
  for (const key of ["notificationPreferences", "pushSubscriptions", "scheduledNotifications", "announcements", "notificationLogs", "searchLogs", "newsInteractions", "userSessions", "userInteractions", "userProfiles", "newsVectors", "userRecommendations", "analyticsLogs", "generatedReports", "scheduledReports", "systemMetrics", "roles", "permissions", "rolePermissions", "userRoles", "auditLogs"]) {
    if (!Array.isArray(data[key])) {
      data[key] = [];
      changed = true;
    }
  }
  if (Array.isArray(data.articles)) {
    for (const article of data.articles) {
      const before = JSON.stringify([article.view_count, article.share_count, article.search_count, article.search_click_count, article.trend_score]);
      article.view_count = Number(article.view_count || article.viewCount || article.read_count || article.click_count || 0);
      article.share_count = Number(article.share_count || article.shareCount || 0);
      article.search_count = Number(article.search_count || article.searchCount || 0);
      article.search_click_count = Number(article.search_click_count || article.searchClickCount || 0);
      article.trend_score = Number(article.trend_score || article.trendScore || 0);
      article.viewCount = article.view_count;
      article.shareCount = article.share_count;
      article.searchCount = article.search_count;
      article.searchClickCount = article.search_click_count;
      article.trendScore = article.trend_score;
      const after = JSON.stringify([article.view_count, article.share_count, article.search_count, article.search_click_count, article.trend_score]);
      if (before !== after) changed = true;
    }
  }
  if (changed) fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n");
  return { filePath, changed };
}

const results = DB_PATHS.map(migrateFile);
for (const item of results) {
  const label = path.relative(path.join(__dirname, ".."), item.filePath);
  if (item.error) console.error(`${label}: ${item.error}`);
  else if (item.changed) console.log(`${label}: advanced search/notification/analytics alanları eklendi.`);
  else console.log(`${label}: advanced search/analytics/reports/RBAC migration gerekli değil; alanlar zaten mevcut veya dosya atlandı.`);
}
