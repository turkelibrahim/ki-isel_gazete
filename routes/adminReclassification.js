
"use strict";

const AdminReclassificationService = require("../services/adminReclassificationService");

function routeError(json, res, error) {
  const status = Number(error.statusCode || 500);
  return json(res, status, { success: false, error: { code: status === 422 ? "UNPROCESSABLE_ENTITY" : status === 429 ? "RATE_LIMITED" : "ADMIN_RECLASSIFICATION_ERROR", message: error.message } });
}

async function handleAdminReclassificationRoute(req, res, url, helpers = {}) {
  if (!url.pathname.startsWith("/api/admin")) return false;
  const { readBody, json, db, writeDb } = helpers;

  try {
    if (req.method === "GET" && url.pathname === "/api/admin/reclassification/config") {
      return json(res, 200, { success: true, ...AdminReclassificationService.getConfig() });
    }

    if (req.method === "POST" && url.pathname === "/api/admin/auth/login") {
      const body = await readBody(req);
      return json(res, 200, AdminReclassificationService.login(body.username, body.password));
    }

    if (req.method === "POST" && url.pathname === "/api/admin/auth/logout") {
      return json(res, 200, AdminReclassificationService.logout(req));
    }

    if (req.method === "POST" && url.pathname === "/api/admin/auth/refresh") {
      return json(res, 200, AdminReclassificationService.refresh(req));
    }

    if (req.method === "POST" && url.pathname === "/api/admin/reclassify") {
      const body = await readBody(req);
      const result = AdminReclassificationService.reclassify(req, body, db || {});
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 201, result);
    }

    if (req.method === "GET" && url.pathname === "/api/admin/reclassify/queue") {
      return json(res, 200, { success: true, queue: AdminReclassificationService.getQueue(url.searchParams.get("status") || "pending"), status: AdminReclassificationService.queueStatus() });
    }

    const verifyMatch = url.pathname.match(/^\/api\/admin\/verify\/(\d+)$/);
    if (req.method === "POST" && verifyMatch) {
      const body = await readBody(req);
      return json(res, 200, AdminReclassificationService.verifyCorrection(req, Number(verifyMatch[1]), body));
    }

    const recordMatch = url.pathname.match(/^\/api\/admin\/reclassify\/(\d+)$/);
    if (req.method === "GET" && recordMatch) {
      const record = AdminReclassificationService.getQueue(null).find((item) => Number(item.id) === Number(recordMatch[1]));
      return record ? json(res, 200, { success: true, record }) : json(res, 404, { success: false, error: { message: "Düzeltme kaydı bulunamadı." } });
    }

    if (req.method === "GET" && url.pathname === "/api/admin/stats/feedback") {
      return json(res, 200, AdminReclassificationService.feedbackStats());
    }

    if (req.method === "GET" && url.pathname === "/api/admin/stats/corrections") {
      const store = AdminReclassificationService._internal.loadState();
      return json(res, 200, { success: true, admins: store.admins.map((admin) => AdminReclassificationService.adminStats(admin.id)) });
    }

    const adminStatsMatch = url.pathname.match(/^\/api\/admin\/stats\/corrections\/(\d+)$/);
    if (req.method === "GET" && adminStatsMatch) {
      return json(res, 200, { success: true, stats: AdminReclassificationService.adminStats(Number(adminStatsMatch[1])) });
    }

    if (req.method === "GET" && url.pathname === "/api/admin/stats/model") {
      return json(res, 200, AdminReclassificationService.modelStats());
    }

    if (req.method === "GET" && url.pathname === "/api/admin/retraining/status") {
      return json(res, 200, { success: true, threshold: AdminReclassificationService.checkRetrainingThreshold(), model: AdminReclassificationService.modelStats().model, queue: AdminReclassificationService.queueStatus() });
    }

    if (req.method === "POST" && url.pathname === "/api/admin/retraining/trigger") {
      const body = await readBody(req);
      return json(res, 202, AdminReclassificationService.triggerRetraining(req, body));
    }

    if (req.method === "GET" && url.pathname === "/api/admin/retraining/history") {
      return json(res, 200, { success: true, history: AdminReclassificationService._internal.loadState().retrainingTriggers });
    }

    const runMatch = url.pathname.match(/^\/api\/admin\/retraining\/run\/(rt_[\w]+)$/);
    if (req.method === "POST" && runMatch) {
      return json(res, 200, AdminReclassificationService.runRetraining(runMatch[1]));
    }

    return false;
  } catch (error) {
    return routeError(json, res, error);
  }
}

module.exports = { handleAdminReclassificationRoute };
