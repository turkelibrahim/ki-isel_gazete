"use strict";
const fs = require("fs");
const path = require("path");
const ReportService = require("../services/reportService");
const RbacService = require("../services/rbacService");
const ScheduledReportService = require("../services/scheduledReportService");

function apiError(json, res, error) { return json(res, error.statusCode || 500, { success: false, message: error.message || "Rapor işlemi başarısız oldu." }); }
function bodyDateRange(body = {}, url) { return { startDate: body.startDate || body.start_date || url.searchParams.get("startDate") || new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10), endDate: body.endDate || body.end_date || url.searchParams.get("endDate") || new Date().toISOString().slice(0, 10) }; }
async function handleAdminReportsRoute(req, res, url, helpers = {}) {
  if (!url.pathname.startsWith("/api/admin/reports")) return false;
  const { readBody, json, db, writeDb } = helpers;
  ReportService.normalizeDb(db);
  try {
    if (req.method === "GET" && url.pathname === "/api/admin/reports/usage") {
      RbacService.requirePermission(db, req, "reports.view");
      const reportType = url.searchParams.get("reportType") || "full_admin_report";
      const { startDate, endDate } = bodyDateRange({}, url);
      const data = ReportService.collectReportData(db, reportType, startDate, endDate);
      return json(res, 200, data);
    }
    if (req.method === "POST" && (url.pathname === "/api/admin/reports/export/excel" || url.pathname === "/api/admin/reports/export/pdf")) {
      const body = await readBody(req).catch(() => ({}));
      const format = url.pathname.endsWith("/excel") ? "excel" : "pdf";
      const { startDate, endDate } = bodyDateRange(body, url);
      const result = ReportService.generateUsageReport(db, { reportType: body.reportType || body.report_type || "full_admin_report", startDate, endDate, format, req });
      writeDb?.(db);
      return json(res, 201, { success: true, message: `${format.toUpperCase()} raporu oluşturuldu.`, data: result.report, file: result.file });
    }
    if (req.method === "GET" && url.pathname === "/api/admin/reports/generated") {
      RbacService.requirePermission(db, req, "reports.view");
      return json(res, 200, { success: true, count: db.generatedReports.length, data: [...db.generatedReports].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)) });
    }
    const downloadMatch = url.pathname.match(/^\/api\/admin\/reports\/([^/]+)\/download$/);
    if (req.method === "GET" && downloadMatch) {
      const { record, filePath } = ReportService.getReportFilePath(db, decodeURIComponent(downloadMatch[1]), req);
      const ext = path.extname(filePath).toLowerCase();
      const contentType = ext === ".pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      res.writeHead(200, { "Content-Type": contentType, "Content-Disposition": `attachment; filename="${path.basename(filePath)}"`, "Cache-Control": "no-store" });
      fs.createReadStream(filePath).pipe(res);
      return true;
    }
    if (req.method === "POST" && url.pathname === "/api/admin/reports/scheduled") {
      const user = RbacService.requirePermission(db, req, "reports.schedule");
      const body = await readBody(req).catch(() => ({}));
      const schedule = ScheduledReportService.upsertScheduledReport(db, body, user);
      writeDb?.(db);
      return json(res, 201, { success: true, message: "Zamanlanmış rapor oluşturuldu.", data: schedule });
    }
    if (req.method === "GET" && url.pathname === "/api/admin/reports/scheduled") {
      RbacService.requirePermission(db, req, "reports.view");
      return json(res, 200, { success: true, count: db.scheduledReports.length, data: db.scheduledReports });
    }
    return false;
  } catch (error) { return apiError(json, res, error); }
}
module.exports = { handleAdminReportsRoute };
