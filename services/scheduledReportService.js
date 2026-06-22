"use strict";
const crypto = require("crypto");
const ReportService = require("./reportService");
const RbacService = require("./rbacService");
const ReportEmailService = require("./reportEmailService");

const DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
function nowIso() { return new Date().toISOString(); }
function id(prefix) { return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`; }
function normalizeDb(db = {}) { ReportService.normalizeDb(db); db.scheduledReports = Array.isArray(db.scheduledReports) ? db.scheduledReports : []; return db; }
function parseTime(value = "08:00") { const m = String(value || "").match(/^([01]?\d|2[0-3]):([0-5]\d)$/); if (!m) throw Object.assign(new Error("Saat formatı HH:mm olmalıdır."), { statusCode: 422 }); return { h: Number(m[1]), m: Number(m[2]) }; }
function calculateNextRunAt({ frequency = "daily", scheduled_time = "08:00", scheduled_day = "monday", timezone = "Europe/Istanbul", now = new Date() } = {}) {
  const { h, m } = parseTime(scheduled_time);
  const next = new Date(now);
  next.setSeconds(0, 0); next.setHours(h, m, 0, 0);
  if (frequency === "daily") { if (next <= now) next.setDate(next.getDate() + 1); return next.toISOString(); }
  if (frequency === "weekly") {
    const target = DAYS.indexOf(String(scheduled_day || "").toLowerCase());
    if (target < 0) throw Object.assign(new Error("Haftalık rapor için geçerli gün seçilmelidir."), { statusCode: 422 });
    let diff = (target - next.getDay() + 7) % 7;
    next.setDate(next.getDate() + diff);
    if (next <= now) next.setDate(next.getDate() + 7);
    return next.toISOString();
  }
  if (frequency === "monthly") { next.setDate(1); if (next <= now) next.setMonth(next.getMonth() + 1); return next.toISOString(); }
  throw Object.assign(new Error("Geçersiz rapor frekansı."), { statusCode: 422 });
}
function dateRangeForFrequency(frequency, now = new Date()) {
  const end = new Date(now); const start = new Date(now);
  if (frequency === "monthly") { start.setMonth(start.getMonth() - 1); }
  else if (frequency === "weekly") { start.setDate(start.getDate() - 7); }
  else { start.setDate(start.getDate() - 1); }
  return { startDate: start.toISOString().slice(0, 10), endDate: end.toISOString().slice(0, 10) };
}
function upsertScheduledReport(db, payload = {}, currentUser = { id: "system" }) {
  normalizeDb(db);
  const frequency = payload.frequency || "daily";
  const format = payload.format || "excel";
  const reportType = payload.report_type || payload.reportType || "full_admin_report";
  if (!ReportService.REPORT_TYPES.has(reportType)) throw Object.assign(new Error("Geçersiz rapor türü."), { statusCode: 422 });
  if (!ReportService.FORMATS.has(format)) throw Object.assign(new Error("Geçersiz rapor formatı."), { statusCode: 422 });
  parseTime(payload.scheduled_time || payload.scheduledTime || "08:00");
  const schedule = {
    id: payload.id || id("sched_report"), created_by_user_id: currentUser.id, report_type: reportType, frequency, format,
    recipients_json: Array.isArray(payload.recipients) ? payload.recipients : [],
    scheduled_time: payload.scheduled_time || payload.scheduledTime || "08:00",
    scheduled_day: payload.scheduled_day || payload.scheduledDay || (frequency === "weekly" ? "monday" : null),
    timezone: payload.timezone || process.env.REPORT_DEFAULT_TIMEZONE || "Europe/Istanbul",
    is_active: payload.is_active !== false && payload.isActive !== false,
    last_run_at: null,
    next_run_at: calculateNextRunAt({ frequency, scheduled_time: payload.scheduled_time || payload.scheduledTime || "08:00", scheduled_day: payload.scheduled_day || payload.scheduledDay || "monday" }),
    created_at: nowIso(), updated_at: nowIso()
  };
  db.scheduledReports.push(schedule);
  RbacService.createAuditLog(db, { actor_user_id: currentUser.id, action: "scheduled_report.created", target_type: "scheduled_report", target_id: schedule.id, new_value_json: schedule });
  return schedule;
}
function alreadyGeneratedThisPeriod(db, schedule, now = new Date()) {
  const key = schedule.frequency === "monthly" ? now.toISOString().slice(0, 7) : schedule.frequency === "weekly" ? `${now.getUTCFullYear()}-W${Math.ceil((((now - new Date(Date.UTC(now.getUTCFullYear(),0,1))) / 86400000) + new Date(Date.UTC(now.getUTCFullYear(),0,1)).getUTCDay()+1)/7)}` : now.toISOString().slice(0, 10);
  return db.generatedReports.some((r) => r.scheduled_report_id === schedule.id && r.period_key === key && r.status === "success");
}
async function runDueScheduledReports(db, { now = new Date(), logWarn } = {}) {
  normalizeDb(db);
  const due = db.scheduledReports.filter((s) => s.is_active && s.next_run_at && new Date(s.next_run_at) <= now);
  const results = [];
  for (const schedule of due) {
    try {
      if (alreadyGeneratedThisPeriod(db, schedule, now)) { schedule.next_run_at = calculateNextRunAt({ ...schedule, scheduled_time: schedule.scheduled_time, now }); results.push({ schedule_id: schedule.id, skipped: true }); continue; }
      const range = dateRangeForFrequency(schedule.frequency, now);
      const currentUser = { id: schedule.created_by_user_id || "system" };
      const result = ReportService.generateUsageReport(db, { reportType: schedule.report_type, startDate: range.startDate, endDate: range.endDate, format: schedule.format, currentUser });
      result.report.scheduled_report_id = schedule.id;
      result.report.period_key = schedule.frequency === "monthly" ? now.toISOString().slice(0, 7) : now.toISOString().slice(0, 10);
      const email = await ReportEmailService.sendReportEmail(schedule.recipients_json, result.report);
      if (!email.success && !email.skipped) result.report.error_message = email.error || "Rapor e-postası gönderilemedi.";
      schedule.last_run_at = nowIso();
      schedule.next_run_at = calculateNextRunAt({ ...schedule, scheduled_time: schedule.scheduled_time, now });
      schedule.updated_at = nowIso();
      results.push({ schedule_id: schedule.id, report_id: result.report.id, email });
    } catch (error) {
      logWarn?.("scheduled-reports", "scheduled report failed", error.message || String(error));
      results.push({ schedule_id: schedule.id, success: false, error: error.message || String(error) });
    }
  }
  return results;
}
function startScheduledReportScheduler({ readDb, writeDb, intervalMs = Number(process.env.REPORT_SCHEDULER_INTERVAL_MS || 60000), logWarn } = {}) {
  if (process.env.REPORTS_ENABLED === "false") return null;
  if (typeof readDb !== "function" || typeof writeDb !== "function") return null;
  const timer = setInterval(async () => { try { const db = readDb(); await runDueScheduledReports(db, { logWarn }); writeDb(db); } catch (e) { logWarn?.("scheduled-reports", "scheduler failed", e.message || String(e)); } }, Math.max(10000, intervalMs));
  timer.unref?.(); return timer;
}
module.exports = { normalizeDb, calculateNextRunAt, dateRangeForFrequency, upsertScheduledReport, runDueScheduledReports, startScheduledReportScheduler };
