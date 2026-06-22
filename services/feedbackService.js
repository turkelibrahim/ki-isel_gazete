"use strict";

const crypto = require("crypto");
const {
  ensureFeedbackCollections,
  listFeedback,
  saveFeedback,
  findFeedback,
  addNotification,
  addAuditLog
} = require("../db/feedbackRepository");

const FEEDBACK_TYPES = new Set(["Öneri", "Hata Bildirimi", "Şikayet", "Yeni Özellik", "Memnuniyet", "Genel Mesaj"]);
const PRIORITIES = new Set(["Düşük", "Normal", "Önemli", "Acil"]);
const STATUSES = new Set(["Gönderildi", "Görüldü", "İnceleniyor", "Cevaplandı", "Çözüldü", "Kapatıldı"]);

function nowIso() {
  return new Date().toISOString();
}

function stripHtml(value = "") {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeMeta(meta = {}) {
  const safe = {};
  const allowed = ["pageName", "currentUrl", "userAgent", "deviceType", "articleId", "eventId", "screen", "language"];
  for (const key of allowed) {
    const value = meta?.[key];
    if (value === undefined || value === null || value === "") continue;
    safe[key] = stripHtml(value).slice(0, key === "userAgent" ? 300 : 180);
  }
  return safe;
}

function publicFeedback(item, { includeTechnical = false, includeInternal = false } = {}) {
  if (!item) return null;
  const payload = {
    id: item.id,
    userId: item.userId,
    userName: item.userName,
    userEmail: item.userEmail,
    subject: item.subject,
    type: item.type,
    priority: item.priority,
    rating: item.rating,
    message: item.message,
    status: item.status,
    adminReply: item.adminReply || "",
    adminReplyAt: item.adminReplyAt || null,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
    archived: Boolean(item.archived)
  };
  if (includeTechnical) payload.technical = item.technical || {};
  if (includeInternal) payload.internalNote = item.internalNote || "";
  return payload;
}

function validateFeedbackInput(body = {}) {
  const subject = stripHtml(body.subject).slice(0, 160);
  const message = stripHtml(body.message).slice(0, 1200);
  const type = stripHtml(body.type);
  const priority = stripHtml(body.priority || "Normal");
  const ratingRaw = Number(body.rating || body.satisfaction || 0);
  const rating = Number.isFinite(ratingRaw) ? Math.max(0, Math.min(5, Math.round(ratingRaw))) : 0;

  if (!subject || subject.length < 3) throw Object.assign(new Error("Konu en az 3 karakter olmalı."), { statusCode: 400 });
  if (!message || message.length < 10) throw Object.assign(new Error("Mesaj en az 10 karakter olmalı."), { statusCode: 400 });
  if (message.length > 1000) throw Object.assign(new Error("Mesaj en fazla 1000 karakter olabilir."), { statusCode: 400 });
  if (!FEEDBACK_TYPES.has(type)) throw Object.assign(new Error("Geçerli bir geri bildirim türü seçmelisin."), { statusCode: 400 });
  if (!PRIORITIES.has(priority)) throw Object.assign(new Error("Geçerli bir öncelik seçmelisin."), { statusCode: 400 });

  return { subject, message, type, priority, rating };
}

function createFeedback(db, body, user, requestMeta = {}) {
  ensureFeedbackCollections(db);
  if (!user?.id) throw Object.assign(new Error("Geri bildirim göndermek için giriş yapmalısın."), { statusCode: 401 });
  const input = validateFeedbackInput(body);
  const timestamp = nowIso();
  const feedback = {
    id: `fb_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`,
    userId: user.id,
    userName: stripHtml(user.name || "Kullanıcı").slice(0, 120),
    userEmail: stripHtml(user.email || "").slice(0, 180),
    subject: input.subject,
    type: input.type,
    priority: input.priority,
    rating: input.rating,
    message: input.message,
    status: "Gönderildi",
    technical: normalizeMeta({ ...requestMeta, ...(body.meta || {}) }),
    adminReply: "",
    adminReplyAt: null,
    adminReplyBy: null,
    internalNote: "",
    archived: false,
    createdAt: timestamp,
    updatedAt: timestamp
  };
  saveFeedback(db, feedback);
  return publicFeedback(feedback, { includeTechnical: false });
}

function listMyFeedback(db, userId, { page = 1, pageSize = 20 } = {}) {
  ensureFeedbackCollections(db);
  const safePage = Math.max(1, Number(page) || 1);
  const safePageSize = Math.min(100, Math.max(1, Number(pageSize) || 20));
  const items = listFeedback(db)
    .filter((item) => String(item.userId) === String(userId) && !item.archived)
    .sort((a, b) => new Date(b.updatedAt || b.createdAt) - new Date(a.updatedAt || a.createdAt));
  const offset = (safePage - 1) * safePageSize;
  return {
    items: items.slice(offset, offset + safePageSize).map((item) => publicFeedback(item)),
    page: safePage,
    pageSize: safePageSize,
    total: items.length,
    hasNext: offset + safePageSize < items.length
  };
}

function getMyFeedback(db, userId, id) {
  const item = findFeedback(db, id);
  if (!item || String(item.userId) !== String(userId) || item.archived) {
    throw Object.assign(new Error("Geri bildirim bulunamadı."), { statusCode: 404 });
  }
  return publicFeedback(item);
}

function listAdminFeedback(db, { page = 1, pageSize = 30, status = "", type = "", priority = "", includeArchived = false } = {}) {
  ensureFeedbackCollections(db);
  const safePage = Math.max(1, Number(page) || 1);
  const safePageSize = Math.min(100, Math.max(1, Number(pageSize) || 30));
  let items = listFeedback(db).filter((item) => includeArchived || !item.archived);
  if (status) items = items.filter((item) => item.status === status);
  if (type) items = items.filter((item) => item.type === type);
  if (priority) items = items.filter((item) => item.priority === priority);
  items = items.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  const offset = (safePage - 1) * safePageSize;
  return {
    items: items.slice(offset, offset + safePageSize).map((item) => publicFeedback(item, { includeTechnical: true, includeInternal: true })),
    page: safePage,
    pageSize: safePageSize,
    total: items.length,
    hasNext: offset + safePageSize < items.length
  };
}

function getAdminFeedback(db, id) {
  const item = findFeedback(db, id);
  if (!item) throw Object.assign(new Error("Geri bildirim bulunamadı."), { statusCode: 404 });
  return publicFeedback(item, { includeTechnical: true, includeInternal: true });
}

function updateStatus(db, id, status, adminUser) {
  const item = findFeedback(db, id);
  if (!item) throw Object.assign(new Error("Geri bildirim bulunamadı."), { statusCode: 404 });
  const cleanStatus = stripHtml(status);
  if (!STATUSES.has(cleanStatus)) throw Object.assign(new Error("Geçerli bir durum seçmelisin."), { statusCode: 400 });
  item.status = cleanStatus;
  item.updatedAt = nowIso();
  addAuditLog(db, {
    id: `audit_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    userId: adminUser?.id || "admin",
    action: "UPDATE_FEEDBACK_STATUS",
    resourceType: "feedback",
    resourceId: item.id,
    details: { status: cleanStatus },
    timestamp: item.updatedAt
  });
  return publicFeedback(item, { includeTechnical: true, includeInternal: true });
}

function replyFeedback(db, id, reply, adminUser) {
  const item = findFeedback(db, id);
  if (!item) throw Object.assign(new Error("Geri bildirim bulunamadı."), { statusCode: 404 });
  const cleanReply = stripHtml(reply).slice(0, 1000);
  if (cleanReply.length < 2) throw Object.assign(new Error("Cevap boş olamaz."), { statusCode: 400 });
  const timestamp = nowIso();
  item.adminReply = cleanReply;
  item.adminReplyAt = timestamp;
  item.adminReplyBy = adminUser?.id || "admin";
  item.status = "Cevaplandı";
  item.updatedAt = timestamp;
  addNotification(db, {
    id: `notif_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    userId: item.userId,
    type: "feedback_reply",
    title: "Geri bildirim cevabı",
    message: "Admin geri bildiriminize cevap verdi.",
    feedbackId: item.id,
    read: false,
    createdAt: timestamp
  });
  addAuditLog(db, {
    id: `audit_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    userId: adminUser?.id || "admin",
    action: "REPLY_FEEDBACK",
    resourceType: "feedback",
    resourceId: item.id,
    details: { replyPreview: cleanReply.slice(0, 120) },
    timestamp
  });
  return publicFeedback(item, { includeTechnical: true, includeInternal: true });
}

function archiveFeedback(db, id, adminUser) {
  const item = findFeedback(db, id);
  if (!item) throw Object.assign(new Error("Geri bildirim bulunamadı."), { statusCode: 404 });
  const timestamp = nowIso();
  item.archived = true;
  item.status = item.status === "Çözüldü" ? item.status : "Kapatıldı";
  item.updatedAt = timestamp;
  addAuditLog(db, {
    id: `audit_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`,
    userId: adminUser?.id || "admin",
    action: "ARCHIVE_FEEDBACK",
    resourceType: "feedback",
    resourceId: item.id,
    details: {},
    timestamp
  });
  return publicFeedback(item, { includeTechnical: true, includeInternal: true });
}

module.exports = {
  FEEDBACK_TYPES: [...FEEDBACK_TYPES],
  PRIORITIES: [...PRIORITIES],
  STATUSES: [...STATUSES],
  createFeedback,
  listMyFeedback,
  getMyFeedback,
  listAdminFeedback,
  getAdminFeedback,
  updateStatus,
  replyFeedback,
  archiveFeedback,
  stripHtml
};
