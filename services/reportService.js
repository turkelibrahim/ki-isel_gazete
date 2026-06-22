"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { generateExcelReport } = require("./excelReportService");
const { generatePdfReport } = require("./pdfReportService");
const RbacService = require("./rbacService");
const SystemMetricsService = require("./systemMetricsService");
const { reportDir } = require("./reportExportUtils");

const REPORT_TYPES = new Set(["usage_summary", "active_users", "top_news", "category_traffic", "system_metrics", "full_admin_report"]);
const FORMATS = new Set(["excel", "pdf"]);

function nowIso() { return new Date().toISOString(); }
function id(prefix) { return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`; }
function toDate(value, fallback) { const d = new Date(value || fallback || Date.now()); return Number.isNaN(d.getTime()) ? new Date(fallback || Date.now()) : d; }
function dayKey(date) { return new Date(date).toISOString().slice(0, 10); }
function inRange(dateValue, start, end) { const t = toDate(dateValue, 0).getTime(); return t >= start.getTime() && t <= end.getTime(); }
function num(v, f = 0) { const n = Number(v); return Number.isFinite(n) ? n : f; }
function normalizeDb(db = {}) {
  db.generatedReports = Array.isArray(db.generatedReports) ? db.generatedReports : [];
  db.scheduledReports = Array.isArray(db.scheduledReports) ? db.scheduledReports : [];
  SystemMetricsService.normalizeDb(db);
  RbacService.normalizeDb(db);
  return db;
}
function validateDateRange(startDate, endDate) {
  const start = toDate(startDate, Date.now() - 7 * 86400000);
  const end = toDate(endDate, Date.now());
  if (start.getTime() > end.getTime()) {
    const error = new Error("Başlangıç tarihi bitiş tarihinden büyük olamaz.");
    error.statusCode = 422;
    throw error;
  }
  return { start, end };
}
function articleId(article) { return String(article?.id || article?.articleId || article?.news_id || ""); }
function articleTitle(article) { return article?.title || article?.headline || "Başlıksız haber"; }
function articleSource(article) { return article?.source_name || article?.sourceName || article?.source || article?.publisher || "Kaynak belirtilmedi"; }
function articlePublished(article) { return article?.published_at || article?.publishedAt || article?.pubDate || article?.created_at || article?.createdAt || article?.date || ""; }
function interactionKey(item) { return String(item.user_id || item.userId || item.anonymous_id || item.anonymousId || "anonymous"); }
function interactionType(item) { return String(item.interaction_type || item.interactionType || item.type || ""); }
function interactionNewsId(item) { return String(item.news_id || item.newsId || item.article_id || item.articleId || ""); }
function interactionDate(item) { return item.created_at || item.createdAt || item.timestamp || new Date().toISOString(); }
function interactionDuration(item) { return Math.max(0, Math.min(600, num(item.duration_seconds || item.durationSeconds, 0))); }
function relevantInteractions(db, start, end) {
  const userInteractions = Array.isArray(db.userInteractions) ? db.userInteractions : [];
  const newsInteractions = Array.isArray(db.newsInteractions) ? db.newsInteractions : [];
  return [...userInteractions, ...newsInteractions].filter((item) => inRange(interactionDate(item), start, end));
}
function buildArticleMap(db) { return new Map((db.articles || []).map((a) => [articleId(a), a])); }
function calculateDailyActiveUsers(interactions, start, end) {
  const byDay = new Map();
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()));
  const last = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()));
  while (cursor <= last) { byDay.set(dayKey(cursor), new Set()); cursor.setUTCDate(cursor.getUTCDate() + 1); }
  for (const item of interactions) {
    const key = dayKey(interactionDate(item));
    if (!byDay.has(key)) byDay.set(key, new Set());
    byDay.get(key).add(interactionKey(item));
  }
  return [...byDay.entries()].map(([date, users]) => ({ date, active_users: users.size }));
}
function calculateTopNews(db, interactions, start, end) {
  const articles = buildArticleMap(db);
  const map = new Map();
  for (const item of interactions) {
    const type = interactionType(item);
    if (!["view", "click", "read", "search_click", "recommendation_click", "share"].includes(type)) continue;
    const nid = interactionNewsId(item);
    if (!nid) continue;
    const row = map.get(nid) || { news_id: nid, read_count: 0, share_count: 0, total_reading_time: 0, read_events: 0 };
    if (type === "share") row.share_count += 1;
    else row.read_count += 1;
    if (type === "read") { row.total_reading_time += interactionDuration(item); row.read_events += 1; }
    map.set(nid, row);
  }
  for (const article of db.articles || []) {
    const nid = articleId(article);
    if (!map.has(nid)) map.set(nid, { news_id: nid, read_count: num(article.view_count || article.viewCount, 0), share_count: num(article.share_count || article.shareCount, 0), total_reading_time: 0, read_events: 0 });
  }
  return [...map.values()].map((row) => {
    const article = articles.get(row.news_id) || {};
    return {
      ...row,
      title: articleTitle(article),
      category: article.category || "Bilinmeyen kategori",
      source_name: articleSource(article),
      published_at: articlePublished(article),
      average_reading_time_seconds: row.read_events ? Math.round(row.total_reading_time / row.read_events) : 0
    };
  }).sort((a, b) => (b.read_count - a.read_count) || (b.share_count - a.share_count)).slice(0, 25);
}
function calculateCategoryTraffic(db, interactions) {
  const articles = buildArticleMap(db);
  const map = new Map();
  let total = 0;
  for (const item of interactions) {
    const type = interactionType(item);
    if (!["view", "click", "read", "search_click", "recommendation_click"].includes(type)) continue;
    const article = articles.get(interactionNewsId(item)) || {};
    const category = item.category || article.category || "Bilinmeyen kategori";
    const row = map.get(category) || { category, views: 0, reading_time_seconds: 0, topNews: new Map() };
    row.views += 1;
    row.reading_time_seconds += interactionDuration(item);
    const title = articleTitle(article);
    row.topNews.set(title, (row.topNews.get(title) || 0) + 1);
    map.set(category, row);
    total += 1;
  }
  return [...map.values()].map((row) => ({
    category: row.category,
    views: row.views,
    reading_time_seconds: Math.round(row.reading_time_seconds),
    percentage: total ? Math.round((row.views / total) * 10000) / 100 : 0,
    top_news_title: [...row.topNews.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "-"
  })).sort((a, b) => b.views - a.views);
}
function collectReportData(db, reportType = "full_admin_report", startDate, endDate) {
  normalizeDb(db);
  const { start, end } = validateDateRange(startDate, endDate);
  const interactions = relevantInteractions(db, start, end);
  const daily = calculateDailyActiveUsers(interactions, start, end);
  const topNews = calculateTopNews(db, interactions, start, end);
  const categoryTraffic = calculateCategoryTraffic(db, interactions);
  const metrics = (db.systemMetrics || []).filter((m) => inRange(m.created_at, start, end));
  if (!metrics.length) metrics.push(SystemMetricsService.collectSnapshot(db, { scheduler_status: "running" }));
  const readInteractions = interactions.filter((i) => ["view", "click", "read", "search_click", "recommendation_click"].includes(interactionType(i)));
  const shareInteractions = interactions.filter((i) => interactionType(i) === "share");
  const readDurations = interactions.filter((i) => interactionType(i) === "read").map(interactionDuration);
  const summary = {
    daily_active_users: new Set(interactions.map(interactionKey)).size,
    total_interactions: interactions.length,
    total_reads: readInteractions.length,
    total_shares: shareInteractions.length,
    average_reading_time_seconds: readDurations.length ? Math.round(readDurations.reduce((a, b) => a + b, 0) / readDurations.length) : 0,
    generated_at: nowIso()
  };
  return {
    success: true,
    report_type: reportType,
    date_range_start: start.toISOString().slice(0, 10),
    date_range_end: end.toISOString().slice(0, 10),
    summary,
    daily_active_users: daily,
    top_news: topNews,
    category_traffic: categoryTraffic,
    system_metrics: metrics.slice(-100),
    empty: interactions.length === 0
  };
}
function createGeneratedReportRecord(db, { currentUser, reportType, startDate, endDate, format }) {
  normalizeDb(db);
  const record = {
    id: id("report"),
    created_by_user_id: currentUser?.id || "system",
    report_type: reportType,
    title: `${reportType} ${startDate || ""} ${endDate || ""}`.trim(),
    date_range_start: startDate,
    date_range_end: endDate,
    format,
    file_url: "",
    status: "generating",
    error_message: "",
    created_at: nowIso(),
    updated_at: nowIso()
  };
  db.generatedReports.push(record);
  return record;
}
function generateUsageReport(db, { reportType = "full_admin_report", startDate, endDate, format = "excel", currentUser, req } = {}) {
  normalizeDb(db);
  if (!REPORT_TYPES.has(reportType)) throw Object.assign(new Error("Geçersiz rapor türü."), { statusCode: 422 });
  if (!FORMATS.has(format)) throw Object.assign(new Error("Geçersiz rapor formatı."), { statusCode: 422 });
  const permission = format === "excel" ? "reports.export_excel" : "reports.export_pdf";
  if (req) currentUser = RbacService.requirePermission(db, req, permission);
  validateDateRange(startDate, endDate);
  const record = createGeneratedReportRecord(db, { currentUser, reportType, startDate, endDate, format });
  try {
    const data = collectReportData(db, reportType, startDate, endDate);
    const file = format === "excel" ? generateExcelReport(data, record) : generatePdfReport(data, record);
    record.file_url = file.url;
    record.status = "success";
    record.updated_at = nowIso();
    RbacService.createAuditLog(db, { actor_user_id: currentUser?.id || "system", action: `report.export.${format}`, target_type: "generated_report", target_id: record.id, new_value_json: { reportType, format, file_url: file.url } }, req);
    return { success: true, data, report: record, file };
  } catch (error) {
    record.status = "failed";
    record.error_message = error.message || String(error);
    record.updated_at = nowIso();
    throw error;
  }
}
function getReportFilePath(db, reportId, req = null) {
  normalizeDb(db);
  const record = db.generatedReports.find((r) => String(r.id) === String(reportId));
  if (!record) throw Object.assign(new Error("Rapor bulunamadı."), { statusCode: 404 });
  if (req) RbacService.requirePermission(db, req, "reports.view");
  const base = path.resolve(process.cwd(), process.env.REPORT_STORAGE_DIR || "generated-reports");
  const fileName = path.basename(String(record.file_url || ""));
  const resolved = path.resolve(base, fileName);
  if (!resolved.startsWith(base)) throw Object.assign(new Error("Geçersiz dosya yolu."), { statusCode: 403 });
  if (!fs.existsSync(resolved)) throw Object.assign(new Error("Rapor dosyası bulunamadı."), { statusCode: 404 });
  return { record, filePath: resolved };
}
module.exports = { REPORT_TYPES, FORMATS, normalizeDb, validateDateRange, collectReportData, generateUsageReport, getReportFilePath };
