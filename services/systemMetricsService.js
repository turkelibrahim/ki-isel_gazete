"use strict";

const os = require("os");
const fs = require("fs");
const path = require("path");

let requestCount = 0;
let errorCount = 0;
let responseTimeTotal = 0;
let responseTimeSamples = 0;

function nowIso() { return new Date().toISOString(); }
function id(prefix) { return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`; }
function normalizeDb(db = {}) { db.systemMetrics = Array.isArray(db.systemMetrics) ? db.systemMetrics : []; return db; }
function observeRequest({ statusCode = 200, responseTimeMs = 0 } = {}) {
  requestCount += 1;
  if (Number(statusCode) >= 400) errorCount += 1;
  const ms = Number(responseTimeMs);
  if (Number.isFinite(ms) && ms >= 0) { responseTimeTotal += ms; responseTimeSamples += 1; }
}
function diskUsagePercent(root = process.cwd()) {
  try {
    const stat = fs.statSync(root);
    if (!stat) return 0;
  } catch { return 0; }
  return 0;
}
function collectSnapshot(db = {}, extra = {}) {
  normalizeDb(db);
  const mem = process.memoryUsage();
  const avgResponse = responseTimeSamples ? responseTimeTotal / responseTimeSamples : 0;
  const snapshot = {
    id: id("metric"),
    cpu_usage: Math.round((os.loadavg()[0] / Math.max(1, os.cpus().length)) * 10000) / 100,
    memory_usage: Math.round((mem.rss / Math.max(1, os.totalmem())) * 10000) / 100,
    memory_rss_mb: Math.round(mem.rss / 1024 / 1024),
    disk_usage: diskUsagePercent(path.resolve(process.cwd())),
    request_count: requestCount,
    error_count: errorCount,
    average_response_time: Math.round(avgResponse * 100) / 100,
    pdf_generation_count: Array.isArray(db.generatedNewspapers) ? db.generatedNewspapers.filter((p) => p.pdf_file_url || p.file_url).length : 0,
    email_sent_count: Array.isArray(db.notificationLogs) ? db.notificationLogs.filter((l) => l.channel === "email" && l.status === "sent").length : 0,
    report_generation_count: Array.isArray(db.generatedReports) ? db.generatedReports.filter((r) => r.status === "success").length : 0,
    scheduler_status: extra.scheduler_status || "running",
    created_at: nowIso()
  };
  db.systemMetrics.push(snapshot);
  db.systemMetrics = db.systemMetrics.slice(-2000);
  return snapshot;
}
function startSystemMetricsScheduler({ readDb, writeDb, intervalMs = Number(process.env.SYSTEM_METRICS_INTERVAL_MS || 60000), logWarn } = {}) {
  if (process.env.SYSTEM_METRICS_ENABLED === "false") return null;
  if (typeof readDb !== "function" || typeof writeDb !== "function") return null;
  const timer = setInterval(() => {
    try {
      const db = readDb();
      collectSnapshot(db);
      writeDb(db);
    } catch (error) {
      logWarn?.("system-metrics", "metric collection failed", error.message || String(error));
    }
  }, Math.max(10000, intervalMs));
  timer.unref?.();
  return timer;
}
module.exports = { normalizeDb, observeRequest, collectSnapshot, startSystemMetricsScheduler };
