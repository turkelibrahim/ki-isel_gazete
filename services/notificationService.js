"use strict";

const crypto = require("crypto");
const { sendPushNotification } = require("./pushService");
const { sendEmailNotification, renderEmailTemplate, escapeHtml } = require("./emailService");

const DEFAULT_TIMEZONE = process.env.DEFAULT_TIMEZONE || "Europe/Istanbul";
const NOTIFICATION_MAX_RETRY = Math.max(1, Number(process.env.NOTIFICATION_MAX_RETRY || 3));
const NOTIFICATION_RETRY_DELAY_MINUTES = Math.max(1, Number(process.env.NOTIFICATION_RETRY_DELAY_MINUTES || 5));
const VALID_NOTIFICATION_TYPES = new Set(["one_day_before", "one_hour_before", "immediate", "event_start", "critical_announcement", "article_share", "system"]);
const VALID_CHANNELS = new Set(["push", "email"]);
const VALID_STATUSES = new Set(["pending", "sent", "failed", "cancelled", "processing"]);

function nowIso() { return new Date().toISOString(); }
function makeId(prefix) { return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`; }
function normalizeBool(value, fallback = false) { return typeof value === "boolean" ? value : fallback; }
function toIso(value) { const d = new Date(value); return Number.isFinite(d.getTime()) ? d.toISOString() : ""; }
function addMinutes(date, minutes) { return new Date(date.getTime() + minutes * 60000); }
function addHours(date, hours) { return new Date(date.getTime() + hours * 3600000); }
function userIdFromRequest(req) {
  const auth = req?.headers?.authorization || "";
  if (!auth) return "user_demo";
  return "user_demo";
}

function defaultPreferences(userId = "user_demo") {
  const now = nowIso();
  return {
    id: `pref_${String(userId).replace(/[^a-zA-Z0-9_-]/g, "_")}`,
    user_id: String(userId),
    push_enabled: false,
    email_enabled: true,
    critical_announcements_enabled: true,
    event_reminders_enabled: true,
    one_day_before_enabled: true,
    one_hour_before_enabled: true,
    event_start_enabled: false,
    timezone: DEFAULT_TIMEZONE,
    created_at: now,
    updated_at: now
  };
}

function normalizeDb(db = {}) {
  db.notificationPreferences = Array.isArray(db.notificationPreferences) ? db.notificationPreferences : [];
  db.pushSubscriptions = Array.isArray(db.pushSubscriptions) ? db.pushSubscriptions : [];
  db.scheduledNotifications = Array.isArray(db.scheduledNotifications) ? db.scheduledNotifications : [];
  db.announcements = Array.isArray(db.announcements) ? db.announcements : [];
  db.notificationLogs = Array.isArray(db.notificationLogs) ? db.notificationLogs : [];
  db.users = Array.isArray(db.users) ? db.users : [];
  if (!db.users.some((u) => String(u.id) === "user_demo")) {
    db.users.push({ id: "user_demo", name: "Demo Kullanıcı", email: process.env.DEMO_USER_EMAIL || "demo@smartnewspaper.local" });
  }
  return db;
}

function getUser(db = {}, userId = "user_demo") {
  normalizeDb(db);
  return db.users.find((u) => String(u.id) === String(userId)) || { id: userId, name: "Kullanıcı", email: process.env.DEMO_USER_EMAIL || "" };
}

function getNotificationPreferences(db = {}, userId = "user_demo") {
  normalizeDb(db);
  const id = String(userId || "user_demo");
  let pref = db.notificationPreferences.find((p) => String(p.user_id || p.userId) === id);
  if (!pref) {
    pref = defaultPreferences(id);
    db.notificationPreferences.push(pref);
  }
  return pref;
}

function updateNotificationPreferences(db = {}, userId = "user_demo", input = {}) {
  const pref = getNotificationPreferences(db, userId);
  const boolFields = ["push_enabled", "email_enabled", "critical_announcements_enabled", "event_reminders_enabled", "one_day_before_enabled", "one_hour_before_enabled", "event_start_enabled"];
  for (const field of boolFields) {
    if (Object.prototype.hasOwnProperty.call(input, field)) pref[field] = Boolean(input[field]);
    const camel = field.replace(/_([a-z])/g, (_, ch) => ch.toUpperCase());
    if (Object.prototype.hasOwnProperty.call(input, camel)) pref[field] = Boolean(input[camel]);
  }
  pref.timezone = String(input.timezone || pref.timezone || DEFAULT_TIMEZONE);
  pref.updated_at = nowIso();
  return pref;
}

function normalizePushSubscription(raw = {}) {
  const endpoint = String(raw.endpoint || "").trim();
  const p256dh = raw.p256dh_key || raw.p256dhKey || raw.keys?.p256dh || "";
  const auth = raw.auth_key || raw.authKey || raw.keys?.auth || "";
  if (!endpoint || !p256dh || !auth) {
    const error = new Error("Push subscription endpoint/p256dh/auth eksik.");
    error.statusCode = 422;
    throw error;
  }
  return { endpoint, p256dh_key: String(p256dh), auth_key: String(auth) };
}

function subscribePush(db = {}, userId = "user_demo", raw = {}, meta = {}) {
  normalizeDb(db);
  const sub = normalizePushSubscription(raw);
  let existing = db.pushSubscriptions.find((item) => item.endpoint === sub.endpoint && String(item.user_id || item.userId) === String(userId));
  if (!existing) {
    existing = { id: makeId("push"), user_id: String(userId), created_at: nowIso() };
    db.pushSubscriptions.push(existing);
  }
  Object.assign(existing, sub, { user_agent: meta.userAgent || raw.user_agent || "", is_active: true, updated_at: nowIso() });
  const pref = getNotificationPreferences(db, userId);
  pref.push_enabled = true;
  pref.updated_at = nowIso();
  return existing;
}

function unsubscribePush(db = {}, userId = "user_demo", endpoint = "") {
  normalizeDb(db);
  const targets = db.pushSubscriptions.filter((item) => String(item.user_id || item.userId) === String(userId) && (!endpoint || item.endpoint === endpoint));
  for (const item of targets) {
    item.is_active = false;
    item.updated_at = nowIso();
  }
  if (!endpoint) {
    const pref = getNotificationPreferences(db, userId);
    pref.push_enabled = false;
    pref.updated_at = nowIso();
  }
  return { updated: targets.length };
}

function calculateNotificationTimes(eventDate, timezone = DEFAULT_TIMEZONE, now = new Date()) {
  const event = new Date(eventDate);
  if (!Number.isFinite(event.getTime())) return {};
  return {
    oneDayBefore: addHours(event, -24).toISOString(),
    oneHourBefore: addHours(event, -1).toISOString(),
    eventStart: event.toISOString(),
    timezone
  };
}

function duplicateKey(payload = {}) {
  return [payload.user_id, payload.announcement_id || "", payload.event_id || "", payload.article_id || "", payload.notification_type, payload.channel].map((v) => String(v || "")).join("|");
}

function createNotificationIfNotExists(db = {}, payload = {}) {
  normalizeDb(db);
  const channel = VALID_CHANNELS.has(payload.channel) ? payload.channel : "email";
  const type = VALID_NOTIFICATION_TYPES.has(payload.notification_type) ? payload.notification_type : "system";
  const key = duplicateKey({ ...payload, channel, notification_type: type });
  const existing = db.scheduledNotifications.find((n) => n._dedupe_key === key && n.status !== "cancelled");
  if (existing) return { notification: existing, created: false };
  const now = nowIso();
  const notification = {
    id: makeId("notif"),
    user_id: String(payload.user_id || "user_demo"),
    announcement_id: payload.announcement_id || null,
    event_id: payload.event_id || null,
    article_id: payload.article_id || null,
    notification_type: type,
    channel,
    title: String(payload.title || "SmartNewspaper Bildirimi").slice(0, 160),
    message: String(payload.message || "").slice(0, 600),
    html_content: payload.html_content || "",
    target_url: payload.target_url || "/",
    scheduled_at: toIso(payload.scheduled_at || now) || now,
    sent_at: null,
    status: VALID_STATUSES.has(payload.status) ? payload.status : "pending",
    retry_count: 0,
    error_message: "",
    _dedupe_key: key,
    created_at: now,
    updated_at: now
  };
  db.scheduledNotifications.push(notification);
  return { notification, created: true };
}

function channelsForPreference(pref, purpose = "event") {
  const channels = [];
  if (pref.push_enabled) channels.push("push");
  if (pref.email_enabled) channels.push("email");
  return channels;
}

function allUserIds(db = {}) {
  normalizeDb(db);
  const ids = new Set(db.users.map((u) => String(u.id)).filter(Boolean));
  if (!ids.size) ids.add("user_demo");
  return [...ids];
}

function scheduleNotificationsForAnnouncement(db = {}, announcement = {}, options = {}) {
  normalizeDb(db);
  if (!announcement.is_critical && announcement.priority !== "critical") return { success: true, created: 0, skipped: true };
  const now = options.now ? new Date(options.now) : new Date();
  const eventDate = announcement.event_date || announcement.eventDate || announcement.scheduled_at || announcement.published_at || now.toISOString();
  const times = calculateNotificationTimes(eventDate, announcement.timezone || DEFAULT_TIMEZONE, now);
  let created = 0;
  for (const userId of allUserIds(db)) {
    const pref = getNotificationPreferences(db, userId);
    if (!pref.critical_announcements_enabled) continue;
    const candidates = [];
    if (announcement.event_date || announcement.eventDate || announcement.scheduled_at) {
      if (pref.one_day_before_enabled && times.oneDayBefore && new Date(times.oneDayBefore) > now) candidates.push(["one_day_before", times.oneDayBefore]);
      if (pref.one_hour_before_enabled && times.oneHourBefore && new Date(times.oneHourBefore) > now) candidates.push(["one_hour_before", times.oneHourBefore]);
      if (pref.event_start_enabled && times.eventStart && new Date(times.eventStart) > now) candidates.push(["event_start", times.eventStart]);
    }
    candidates.push(["critical_announcement", now.toISOString()]);
    for (const [type, scheduledAt] of candidates) {
      for (const channel of channelsForPreference(pref, "critical")) {
        const result = createNotificationIfNotExists(db, {
          user_id: userId,
          announcement_id: announcement.id,
          notification_type: type,
          channel,
          title: announcement.title || "Kritik Duyuru",
          message: announcement.description || announcement.message || "Kritik duyuru yayınlandı.",
          html_content: "",
          target_url: announcement.target_url || `/announcements/${announcement.id}`,
          scheduled_at: scheduledAt
        });
        if (result.created) created += 1;
      }
    }
  }
  return { success: true, created };
}

function scheduleNotificationsForEvent(db = {}, event = {}, userId = "user_demo", options = {}) {
  normalizeDb(db);
  const pref = getNotificationPreferences(db, userId);
  if (!pref.event_reminders_enabled) return { success: true, created: 0, skipped: true };
  const now = options.now ? new Date(options.now) : new Date();
  const eventDate = event.event_date || event.eventDate || event.start_date || event.date;
  const times = calculateNotificationTimes(eventDate, pref.timezone || DEFAULT_TIMEZONE, now);
  let created = 0;
  const candidates = [];
  if (pref.one_day_before_enabled && times.oneDayBefore && new Date(times.oneDayBefore) > now) candidates.push(["one_day_before", times.oneDayBefore]);
  if (pref.one_hour_before_enabled && times.oneHourBefore && new Date(times.oneHourBefore) > now) candidates.push(["one_hour_before", times.oneHourBefore]);
  if (pref.event_start_enabled && times.eventStart && new Date(times.eventStart) > now) candidates.push(["event_start", times.eventStart]);
  for (const [type, scheduledAt] of candidates) {
    for (const channel of channelsForPreference(pref, "event")) {
      const result = createNotificationIfNotExists(db, {
        user_id: userId,
        event_id: event.id,
        notification_type: type,
        channel,
        title: `Yaklaşan etkinlik: ${event.title || "Etkinlik"}`,
        message: type === "one_hour_before" ? "Etkinliğe 1 saat kaldı." : type === "one_day_before" ? "Etkinliğe 1 gün kaldı." : "Etkinlik başlıyor.",
        target_url: event.target_url || event.ticket_url || `/events/${event.id}`,
        scheduled_at: scheduledAt
      });
      if (result.created) created += 1;
    }
  }
  return { success: true, created };
}

async function sendNotification(db = {}, notification = {}) {
  const pref = getNotificationPreferences(db, notification.user_id);
  if (notification.channel === "email" && !pref.email_enabled) throw new Error("Kullanıcı e-posta bildirimlerini kapatmış.");
  if (notification.channel === "push" && !pref.push_enabled) throw new Error("Kullanıcı push bildirimlerini kapatmış.");
  if (notification.channel === "push") return sendPushNotification(notification, { db });
  if (notification.channel === "email") return sendEmailNotification(notification, { db, user: getUser(db, notification.user_id) });
  throw new Error("Bilinmeyen bildirim kanalı.");
}

async function processDueNotifications(db = {}, options = {}) {
  normalizeDb(db);
  const now = options.now ? new Date(options.now) : new Date();
  const due = db.scheduledNotifications.filter((n) => n.status === "pending" && new Date(n.scheduled_at) <= now).slice(0, Number(options.limit || 50));
  const results = [];
  for (const notification of due) {
    notification.status = "processing";
    notification.updated_at = nowIso();
    try {
      await sendNotification(db, notification);
      notification.status = "sent";
      notification.sent_at = nowIso();
      notification.error_message = "";
      results.push({ id: notification.id, status: "sent" });
    } catch (error) {
      notification.retry_count = Number(notification.retry_count || 0) + 1;
      notification.error_message = String(error.message || error).slice(0, 500);
      if (notification.retry_count < NOTIFICATION_MAX_RETRY) {
        notification.status = "pending";
        notification.scheduled_at = addMinutes(new Date(), NOTIFICATION_RETRY_DELAY_MINUTES).toISOString();
      } else {
        notification.status = "failed";
      }
      results.push({ id: notification.id, status: notification.status, error: notification.error_message });
    }
    notification.updated_at = nowIso();
    db.notificationLogs.push({ id: makeId("nlog"), notification_id: notification.id, user_id: notification.user_id, channel: notification.channel, status: notification.status, error_message: notification.error_message || "", created_at: nowIso() });
  }
  return { processed: results.length, results };
}

function listScheduledNotifications(db = {}, userId = "user_demo", filters = {}) {
  normalizeDb(db);
  const status = filters.status || "";
  return db.scheduledNotifications
    .filter((n) => String(n.user_id) === String(userId))
    .filter((n) => !status || n.status === status)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

function buildNotificationSummary(db = {}, userId = "user_demo") {
  const list = listScheduledNotifications(db, userId);
  return {
    pending: list.filter((n) => n.status === "pending").length,
    sent: list.filter((n) => n.status === "sent").length,
    failed: list.filter((n) => n.status === "failed").length,
    cancelled: list.filter((n) => n.status === "cancelled").length
  };
}

module.exports = {
  DEFAULT_TIMEZONE,
  VALID_NOTIFICATION_TYPES,
  VALID_CHANNELS,
  defaultPreferences,
  normalizeDb,
  getUser,
  userIdFromRequest,
  getNotificationPreferences,
  updateNotificationPreferences,
  subscribePush,
  unsubscribePush,
  calculateNotificationTimes,
  createNotificationIfNotExists,
  scheduleNotificationsForAnnouncement,
  scheduleNotificationsForEvent,
  processDueNotifications,
  listScheduledNotifications,
  buildNotificationSummary,
  renderEmailTemplate,
  escapeHtml,
  _internal: { makeId, duplicateKey }
};
