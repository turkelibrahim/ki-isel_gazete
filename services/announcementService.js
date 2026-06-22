"use strict";

const NotificationService = require("./notificationService");

function nowIso() { return new Date().toISOString(); }
function makeAnnouncementId() { return `ann_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`; }

function normalizeDb(db = {}) {
  NotificationService.normalizeDb(db);
  db.announcements = Array.isArray(db.announcements) ? db.announcements : [];
  return db;
}

function createAnnouncement(db = {}, input = {}, options = {}) {
  normalizeDb(db);
  const title = String(input.title || "").trim();
  if (!title) {
    const error = new Error("Duyuru başlığı zorunludur.");
    error.statusCode = 422;
    throw error;
  }
  const now = nowIso();
  const announcement = {
    id: input.id || makeAnnouncementId(),
    title,
    description: String(input.description || input.message || "").trim(),
    event_date: input.event_date || input.eventDate || input.scheduled_at || null,
    is_critical: Boolean(input.is_critical || input.isCritical || input.priority === "critical"),
    priority: input.priority || (input.is_critical ? "critical" : "normal"),
    target_url: input.target_url || input.targetUrl || "",
    created_by: options.adminId || "system",
    created_at: now,
    updated_at: now
  };
  db.announcements.push(announcement);
  const scheduled = NotificationService.scheduleNotificationsForAnnouncement(db, announcement);
  return { success: true, announcement, scheduled };
}

function updateAnnouncement(db = {}, id = "", input = {}) {
  normalizeDb(db);
  const announcement = db.announcements.find((item) => String(item.id) === String(id));
  if (!announcement) {
    const error = new Error("Duyuru bulunamadı.");
    error.statusCode = 404;
    throw error;
  }
  const oldDate = announcement.event_date;
  for (const field of ["title", "description", "event_date", "priority", "target_url"]) {
    if (Object.prototype.hasOwnProperty.call(input, field)) announcement[field] = input[field];
  }
  if (Object.prototype.hasOwnProperty.call(input, "is_critical")) announcement.is_critical = Boolean(input.is_critical);
  announcement.updated_at = nowIso();
  let cancelled = 0;
  if (oldDate !== announcement.event_date) {
    for (const notification of db.scheduledNotifications || []) {
      if (String(notification.announcement_id) === String(id) && notification.status === "pending") {
        notification.status = "cancelled";
        notification.updated_at = nowIso();
        cancelled += 1;
      }
    }
  }
  const scheduled = NotificationService.scheduleNotificationsForAnnouncement(db, announcement);
  return { success: true, announcement, cancelled, scheduled };
}

function deleteAnnouncement(db = {}, id = "") {
  normalizeDb(db);
  const before = db.announcements.length;
  db.announcements = db.announcements.filter((item) => String(item.id) !== String(id));
  if (db.announcements.length === before) {
    const error = new Error("Duyuru bulunamadı.");
    error.statusCode = 404;
    throw error;
  }
  let cancelled = 0;
  for (const notification of db.scheduledNotifications || []) {
    if (String(notification.announcement_id) === String(id) && notification.status === "pending") {
      notification.status = "cancelled";
      notification.updated_at = nowIso();
      cancelled += 1;
    }
  }
  return { success: true, cancelled };
}

function listAnnouncements(db = {}) {
  normalizeDb(db);
  return [...db.announcements].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

module.exports = { normalizeDb, createAnnouncement, updateAnnouncement, deleteAnnouncement, listAnnouncements };
