"use strict";

function ensureFeedbackCollections(db) {
  if (!Array.isArray(db.feedbackMessages)) db.feedbackMessages = [];
  if (!Array.isArray(db.notifications)) db.notifications = [];
  if (!Array.isArray(db.auditLog)) db.auditLog = [];
  return db;
}

function listFeedback(db) {
  ensureFeedbackCollections(db);
  return db.feedbackMessages;
}

function saveFeedback(db, feedback) {
  ensureFeedbackCollections(db);
  db.feedbackMessages.push(feedback);
  return feedback;
}

function findFeedback(db, id) {
  ensureFeedbackCollections(db);
  return db.feedbackMessages.find((item) => String(item.id) === String(id));
}

function addNotification(db, notification) {
  ensureFeedbackCollections(db);
  db.notifications.push(notification);
  if (db.notifications.length > 500) db.notifications = db.notifications.slice(-500);
  return notification;
}

function addAuditLog(db, audit) {
  ensureFeedbackCollections(db);
  db.auditLog.push(audit);
  if (db.auditLog.length > 1000) db.auditLog = db.auditLog.slice(-1000);
  return audit;
}

module.exports = {
  ensureFeedbackCollections,
  listFeedback,
  saveFeedback,
  findFeedback,
  addNotification,
  addAuditLog
};
