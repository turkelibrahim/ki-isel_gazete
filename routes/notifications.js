"use strict";

const NotificationService = require("../services/notificationService");

function apiError(json, res, error) {
  return json(res, error.statusCode || 500, { success: false, message: error.message || "Bildirim işlemi başarısız oldu." });
}

async function handleNotificationsRoute(req, res, url, helpers = {}) {
  if (!url.pathname.startsWith("/api/notifications")) return false;
  const { readBody, json, db, writeDb } = helpers;
  const userId = NotificationService.userIdFromRequest(req);
  NotificationService.normalizeDb(db);

  try {
    if (req.method === "GET" && url.pathname === "/api/notifications/preferences") {
      const preferences = NotificationService.getNotificationPreferences(db, userId);
      return json(res, 200, { success: true, data: preferences, vapidPublicKey: process.env.VAPID_PUBLIC_KEY || "" });
    }

    if (req.method === "POST" && url.pathname === "/api/notifications/preferences") {
      const body = await readBody(req);
      const preferences = NotificationService.updateNotificationPreferences(db, userId, body || {});
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 200, { success: true, message: "Bildirim tercihleri kaydedildi.", data: preferences });
    }

    if (req.method === "POST" && url.pathname === "/api/notifications/push/subscribe") {
      const body = await readBody(req);
      const subscription = NotificationService.subscribePush(db, userId, body || {}, { userAgent: req.headers["user-agent"] || "" });
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 201, { success: true, message: "Push aboneliği kaydedildi.", data: subscription });
    }

    if (req.method === "DELETE" && url.pathname === "/api/notifications/push/unsubscribe") {
      let body = {};
      try { body = await readBody(req); } catch { body = {}; }
      const result = NotificationService.unsubscribePush(db, userId, body.endpoint || url.searchParams.get("endpoint") || "");
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 200, { success: true, message: "Push aboneliği kapatıldı.", ...result });
    }

    if (req.method === "POST" && url.pathname === "/api/notifications/test") {
      const pref = NotificationService.getNotificationPreferences(db, userId);
      const body = await readBody(req).catch(() => ({}));
      const channels = [];
      if (body.channel) channels.push(body.channel);
      else {
        if (pref.push_enabled) channels.push("push");
        if (pref.email_enabled) channels.push("email");
      }
      if (!channels.length) channels.push("email");
      const created = [];
      for (const channel of channels) {
        if (!NotificationService.VALID_CHANNELS.has(channel)) continue;
        const { notification } = NotificationService.createNotificationIfNotExists(db, {
          user_id: userId,
          article_id: `test_${Date.now()}`,
          notification_type: "system",
          channel,
          title: "SmartNewspaper test bildirimi",
          message: "Bildirim ayarların başarıyla test edildi.",
          target_url: "/#notifications",
          scheduled_at: new Date().toISOString()
        });
        created.push(notification);
      }
      await NotificationService.processDueNotifications(db, { limit: 10 });
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 200, { success: true, message: "Test bildirimi kuyruğa alındı.", data: created });
    }

    if (req.method === "GET" && url.pathname === "/api/notifications/scheduled") {
      const status = url.searchParams.get("status") || "";
      const list = NotificationService.listScheduledNotifications(db, userId, { status });
      return json(res, 200, { success: true, count: list.length, data: list, summary: NotificationService.buildNotificationSummary(db, userId) });
    }

    if (req.method === "POST" && url.pathname === "/api/notifications/schedule") {
      const body = await readBody(req);
      const channels = Array.isArray(body.channels) && body.channels.length ? body.channels : [body.channel || "email"];
      const created = [];
      for (const channel of channels) {
        const { notification, created: didCreate } = NotificationService.createNotificationIfNotExists(db, {
          ...body,
          user_id: body.user_id || userId,
          channel,
          notification_type: body.notification_type || body.type || "system",
          scheduled_at: body.scheduled_at || body.scheduledAt || new Date().toISOString()
        });
        if (didCreate) created.push(notification);
      }
      if (typeof writeDb === "function") writeDb(db);
      return json(res, 201, { success: true, count: created.length, data: created });
    }

    return false;
  } catch (error) {
    return apiError(json, res, error);
  }
}

module.exports = { handleNotificationsRoute };
