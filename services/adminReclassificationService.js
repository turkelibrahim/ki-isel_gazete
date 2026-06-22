
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ALLOWED_CATEGORIES = Object.freeze([
  "Teknoloji", "Siyaset", "Spor", "Ekonomi", "Eğlence", "Sağlık", "Bilim", "Dünya", "Yaşam"
]);
const ALLOWED_SET = new Set(ALLOWED_CATEGORIES);
const ROLE_PERMISSIONS = Object.freeze({
  reviewer: { can_reclassify: true, can_verify: false, can_trigger_retrain: false, can_view_stats: true, max_corrections_per_day: 200, feedback_weight: 1.0 },
  editor: { can_reclassify: true, can_verify: true, can_trigger_retrain: false, can_view_stats: true, max_corrections_per_day: 500, feedback_weight: 1.2 },
  super_admin: { can_reclassify: true, can_verify: true, can_trigger_retrain: true, can_view_stats: true, max_corrections_per_day: 9999, feedback_weight: 1.5 }
});
const RETRAINING_TRIGGERS = Object.freeze({ count_threshold: Number(process.env.RECLASSIFICATION_RETRAIN_THRESHOLD || 100), daily_rate_threshold: Number(process.env.RECLASSIFICATION_DAILY_RATE_THRESHOLD || 30), accuracy_threshold: Number(process.env.RECLASSIFICATION_ACCURACY_THRESHOLD || 0.80) });
const ACCURACY_DROP_TOLERANCE = Number(process.env.RECLASSIFICATION_ACCURACY_DROP_TOLERANCE || 0.02);
const TOKEN_EXPIRE_HOURS = Number(process.env.ADMIN_TOKEN_EXPIRE_HOURS || 8);
const MAX_FAILED_LOGIN_ATTEMPTS = Number(process.env.ADMIN_MAX_FAILED_LOGIN_ATTEMPTS || 5);
const RATE_LIMIT_PER_MINUTE = Number(process.env.ADMIN_RATE_LIMIT_PER_MINUTE || 60);
const STORE_PATH = process.env.RECLASSIFICATION_STORE_PATH || path.join(__dirname, "..", "db", "admin_reclassification.json");
const ADMIN_JWT_SECRET = process.env.ADMIN_JWT_SECRET || process.env.SESSION_SECRET || "dev-admin-secret-change-me";

let persistEnabled = true;
let state = null;
const rateLimits = new Map();

function nowIso() { return new Date().toISOString(); }
function todayKey(date = new Date()) { return date.toISOString().slice(0, 10); }
function safeArray(value) { return Array.isArray(value) ? value : []; }
function stableId(seed) { return crypto.createHash("sha256").update(String(seed), "utf8").digest("hex").slice(0, 16); }

function hashPassword(password, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.pbkdf2Sync(String(password), salt, 120000, 32, "sha256").toString("hex");
  return `pbkdf2_sha256$${salt}$${hash}`;
}

function verifyPassword(password, storedHash) {
  const parts = String(storedHash || "").split("$");
  if (parts.length !== 3 || parts[0] !== "pbkdf2_sha256") return false;
  return crypto.timingSafeEqual(Buffer.from(hashPassword(password, parts[1]).split("$")[2]), Buffer.from(parts[2]));
}

function base64Url(input) { return Buffer.from(input).toString("base64url"); }
function signToken(payload) {
  const body = base64Url(JSON.stringify({ ...payload, exp: Date.now() + TOKEN_EXPIRE_HOURS * 3600 * 1000 }));
  const sig = crypto.createHmac("sha256", ADMIN_JWT_SECRET).update(body).digest("hex");
  return `${body}.${sig}`;
}

function verifyToken(token) {
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) throw statusError(401, "Geçersiz token.");
  const expected = crypto.createHmac("sha256", ADMIN_JWT_SECRET).update(body).digest("hex");
  if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) throw statusError(401, "Geçersiz token imzası.");
  const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  if (payload.exp < Date.now()) throw statusError(401, "JWT süresi doldu.");
  return payload;
}

function statusError(statusCode, message, extra = {}) {
  const error = new Error(message);
  error.statusCode = statusCode;
  Object.assign(error, extra);
  return error;
}

function defaultState() {
  const bootstrapPassword = process.env.ADMIN_BOOTSTRAP_PASSWORD || "admin123";
  return {
    nextRecordId: 1,
    nextBatchId: 1,
    admins: [
      { id: 1, username: "reviewer", email: "reviewer@smartnewspaper.local", passwordHash: hashPassword(bootstrapPassword), role: "reviewer", isActive: true, totalCorrections: 0, accuracyRate: 1, failedLoginAttempts: 0, lockedUntil: null, lastLogin: null },
      { id: 2, username: "editor", email: "editor@smartnewspaper.local", passwordHash: hashPassword(bootstrapPassword), role: "editor", isActive: true, totalCorrections: 0, accuracyRate: 1, failedLoginAttempts: 0, lockedUntil: null, lastLogin: null },
      { id: 3, username: "superadmin", email: "superadmin@smartnewspaper.local", passwordHash: hashPassword(bootstrapPassword), role: "super_admin", isActive: true, totalCorrections: 0, accuracyRate: 1, failedLoginAttempts: 0, lockedUntil: null, lastLogin: null }
    ],
    sessions: [],
    records: [],
    feedbackBatches: [],
    trainingExamples: [],
    retrainingTriggers: [],
    adminLog: [],
    securityLog: [],
    deadLetterQueue: [],
    modelState: { currentVersion: "baseline", oldVersion: "baseline", currentAccuracy: 0.86, oldAccuracy: 0.86, retrainingRunning: false }
  };
}

function loadState() {
  if (state) return state;
  if (persistEnabled && fs.existsSync(STORE_PATH)) {
    try {
      state = { ...defaultState(), ...JSON.parse(fs.readFileSync(STORE_PATH, "utf8")) };
      return state;
    } catch { /* fallback below */ }
  }
  state = defaultState();
  saveState();
  return state;
}

function saveState() {
  if (!persistEnabled || !state) return;
  fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(state, null, 2), "utf8");
}

function sanitizeAdmin(admin) {
  if (!admin) return null;
  const { passwordHash, ...safe } = admin;
  return safe;
}

function logAdmin(event, payload = {}) { loadState().adminLog.push({ event, ...payload, at: nowIso() }); saveState(); }
function logSecurity(event, payload = {}) { loadState().securityLog.push({ event, ...payload, at: nowIso() }); saveState(); }

function validateLabels(labels) {
  if (!Array.isArray(labels) || labels.length === 0) throw statusError(422, `En az bir kategori seçilmelidir.`);
  const invalid = labels.filter((label) => !ALLOWED_SET.has(label));
  if (invalid.length) throw statusError(422, `Geçersiz kategori. İzin verilenler: ${ALLOWED_CATEGORIES.join(", ")}`, { invalidLabels: invalid });
  if (new Set(labels).size !== labels.length) throw statusError(422, "Aynı kategori iki kez seçilemez.");
  return labels.slice();
}

function extractToken(req) {
  const header = req?.headers?.authorization || req?.headers?.Authorization || "";
  if (header.startsWith("Bearer ")) return header.slice(7).trim();
  return "";
}

function getCurrentAdmin(req) {
  const token = extractToken(req);
  if (!token) throw statusError(401, "Admin token gerekli.");
  const payload = verifyToken(token);
  const store = loadState();
  const admin = store.admins.find((item) => String(item.id) === String(payload.sub));
  if (!admin || !admin.isActive) throw statusError(401, "Admin aktif değil veya bulunamadı.");
  return admin;
}

function requirePermission(admin, permission) {
  if (!ROLE_PERMISSIONS[admin.role]?.[permission]) throw statusError(403, `Bu işlem için ${permission} yetkisi gerekli.`);
}

function checkRateLimit(adminId, limit = RATE_LIMIT_PER_MINUTE) {
  const key = `${adminId}:${Math.floor(Date.now() / 60000)}`;
  const count = (rateLimits.get(key) || 0) + 1;
  rateLimits.set(key, count);
  if (count > limit) throw statusError(429, "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar dene.");
}

function login(username, password) {
  const store = loadState();
  const admin = store.admins.find((item) => item.username === username);
  if (!admin || !admin.isActive) throw statusError(401, "Kullanıcı adı veya şifre hatalı.");
  if (admin.lockedUntil && new Date(admin.lockedUntil).getTime() > Date.now()) throw statusError(423, "Hesap kilitlendi. Yöneticinizle iletişime geçin.");
  if (!verifyPassword(password, admin.passwordHash)) {
    admin.failedLoginAttempts = Number(admin.failedLoginAttempts || 0) + 1;
    if (admin.failedLoginAttempts >= MAX_FAILED_LOGIN_ATTEMPTS) {
      admin.lockedUntil = new Date(Date.now() + 30 * 60 * 1000).toISOString();
      logSecurity("admin_account_locked", { adminId: admin.id, username: admin.username });
      saveState();
      throw statusError(423, "Hesap kilitlendi. Yöneticinizle iletişime geçin.");
    }
    logSecurity("admin_login_failed", { username });
    saveState();
    throw statusError(401, "Kullanıcı adı veya şifre hatalı.");
  }
  admin.failedLoginAttempts = 0;
  admin.lockedUntil = null;
  admin.lastLogin = nowIso();
  const token = signToken({ sub: String(admin.id), role: admin.role, username: admin.username });
  store.sessions.push({ adminId: admin.id, tokenHash: stableId(token), createdAt: nowIso(), expiresAt: new Date(Date.now() + TOKEN_EXPIRE_HOURS * 3600 * 1000).toISOString() });
  logAdmin("admin_login", { adminId: admin.id, username: admin.username });
  saveState();
  return { success: true, token, expires_at: new Date(Date.now() + TOKEN_EXPIRE_HOURS * 3600 * 1000).toISOString(), admin: sanitizeAdmin(admin) };
}

function logout(req) {
  const token = extractToken(req);
  const tokenHash = stableId(token);
  const store = loadState();
  store.sessions = store.sessions.filter((session) => session.tokenHash !== tokenHash);
  saveState();
  return { success: true, message: "Çıkış yapıldı." };
}

function refresh(req) {
  const admin = getCurrentAdmin(req);
  const token = signToken({ sub: String(admin.id), role: admin.role, username: admin.username });
  return { success: true, token, expires_at: new Date(Date.now() + TOKEN_EXPIRE_HOURS * 3600 * 1000).toISOString(), admin: sanitizeAdmin(admin) };
}

function allDbArticles(db = {}) {
  const articles = [];
  if (Array.isArray(db.articles)) articles.push(...db.articles);
  if (Array.isArray(db.clusters)) {
    for (const cluster of db.clusters) {
      if (cluster.main_article) articles.push(cluster.main_article);
      if (cluster.mainArticle) articles.push(cluster.mainArticle);
      if (Array.isArray(cluster.sources)) articles.push(...cluster.sources);
    }
  }
  return articles;
}

function findArticle(db, articleId) {
  return allDbArticles(db).find((article) => String(article.id || article.article_id || article.articleId) === String(articleId));
}

function articleOriginalLabels(article = {}) {
  const labels = [...safeArray(article.labels), ...safeArray(article.predicted_labels), ...safeArray(article.predictedLabels)];
  if (!labels.length && article.category && ALLOWED_SET.has(article.category)) labels.push(article.category);
  return [...new Set(labels.filter((label) => ALLOWED_SET.has(label)))];
}

function needsVerification(article, correctedLabels, admin) {
  const original = new Set(articleOriginalLabels(article));
  const corrected = new Set(correctedLabels);
  const overlap = [...corrected].some((label) => original.has(label));
  return !overlap && admin.role === "reviewer";
}

function latestRecordForArticle(articleId) {
  const store = loadState();
  return store.records
    .filter((record) => String(record.article_id) === String(articleId) && record.feedback_status !== "rejected")
    .sort((a, b) => new Date(b.corrected_at) - new Date(a.corrected_at))[0] || null;
}

function buildCorrectionPayload(record) {
  if (!record) return null;
  return {
    corrected_labels: record.corrected_labels,
    corrected_at: record.corrected_at,
    admin_id: record.admin_id,
    admin_username: record.admin_username,
    is_verified: Boolean(record.is_verified),
    requires_verification: Boolean(record.requires_verification),
    feedback_status: record.feedback_status,
    feedback_weight: record.feedback_weight,
    record_id: record.id
  };
}

function applyCorrectionToArticle(article = {}) {
  const articleId = article.id || article.article_id || article.articleId;
  if (!articleId) return article;
  const record = latestRecordForArticle(articleId);
  if (!record) {
    article.is_admin_corrected = Boolean(article.is_admin_corrected || article.isAdminCorrected);
    article.isAdminCorrected = article.is_admin_corrected;
    return article;
  }
  article.labels = record.corrected_labels.slice();
  article.label_vector = ALLOWED_CATEGORIES.map((label) => article.labels.includes(label) ? 1 : 0);
  article.label_scores = Object.fromEntries(ALLOWED_CATEGORIES.map((label) => [label, article.labels.includes(label) ? 1 : 0]));
  article.category = record.corrected_labels[0] || article.category;
  article.category_confidence = 1;
  article.category_source = "admin_correction";
  article.is_category_reliable = true;
  article.is_admin_corrected = true;
  article.isAdminCorrected = true;
  article.admin_correction = buildCorrectionPayload(record);
  article.adminCorrection = article.admin_correction;
  if (Array.isArray(article.sources)) {
    article.sources = article.sources.map((source) => ({ ...source, labels: source.labels || article.labels, admin_correction: source.admin_correction || null }));
  }
  return article;
}

function applyCorrectionToCluster(cluster = {}) {
  applyCorrectionToArticle(cluster);
  const main = cluster.main_article || cluster.mainArticle;
  if (main) {
    applyCorrectionToArticle(main);
    if (main.is_admin_corrected) {
      cluster.labels = main.labels;
      cluster.category = main.category;
      cluster.admin_correction = main.admin_correction;
      cluster.adminCorrection = main.adminCorrection;
      cluster.is_admin_corrected = true;
      cluster.isAdminCorrected = true;
    }
  }
  if (Array.isArray(cluster.sources)) cluster.sources = cluster.sources.map((source) => applyCorrectionToArticle(source));
  return cluster;
}

function createTrainingExample(article, record) {
  return {
    article_id: record.article_id,
    title: article.title || "",
    content: article.content || article.fullText || article.summary || "",
    labels: record.corrected_labels.slice(),
    label_vector: ALLOWED_CATEGORIES.map((label) => record.corrected_labels.includes(label) ? 1 : 0),
    language: article.detected_lang || article.detectedLang || article.language || "tr",
    is_augmented: false,
    labeled_at: record.corrected_at,
    source: "admin_correction",
    weight: record.feedback_weight
  };
}

function processFeedbackRecord(recordId, db = {}) {
  const store = loadState();
  const record = store.records.find((item) => Number(item.id) === Number(recordId));
  if (!record) {
    store.deadLetterQueue.push({ record_id: recordId, reason: "record_missing", created_at: nowIso() });
    saveState();
    return false;
  }
  const article = findArticle(db, record.article_id);
  if (!article) {
    record.feedback_status = "rejected";
    store.deadLetterQueue.push({ record_id: recordId, reason: "orphan_article", created_at: nowIso() });
    saveState();
    return false;
  }
  if (record.requires_verification && !record.is_verified) {
    saveState();
    return false;
  }
  store.trainingExamples.push(createTrainingExample(article, record));
  record.feedback_status = "processed";
  saveState();
  return true;
}

function reclassify(req, body, db = {}) {
  const admin = getCurrentAdmin(req);
  requirePermission(admin, "can_reclassify");
  checkRateLimit(admin.id);
  let labels;
  try {
    labels = validateLabels(body.corrected_labels || body.correctedLabels || body.labels);
  } catch (error) {
    logSecurity("invalid_category_reclassification", { adminId: admin.id, labels: body.corrected_labels || body.correctedLabels || body.labels, message: error.message });
    throw error;
  }
  const articleId = String(body.article_id || body.articleId || "");
  if (!articleId) throw statusError(422, "article_id zorunludur.");
  const article = findArticle(db, articleId) || body.article;
  if (!article) throw statusError(404, "Makale bulunamadı.");
  const store = loadState();
  const existing = store.records.find((record) => String(record.article_id) === articleId && Number(record.admin_id) === Number(admin.id));
  const requiresVerification = needsVerification(article, labels, admin);
  const feedbackWeight = Number(ROLE_PERMISSIONS[admin.role]?.feedback_weight || 1.0);
  let record;
  if (existing) {
    existing.corrected_labels = labels;
    existing.correction_reason = body.correction_reason || body.correctionReason || null;
    existing.corrected_at = nowIso();
    existing.feedback_status = "pending";
    existing.requires_verification = requiresVerification;
    existing.is_verified = false;
    existing.verified_by = null;
    existing.verified_at = null;
    record = existing;
  } else {
    record = {
      id: store.nextRecordId++,
      article_id: articleId,
      cluster_id: article.cluster_id || article.clusterId || body.cluster_id || body.clusterId || null,
      original_labels: articleOriginalLabels(article),
      original_model: article.category_source || article.label_source || article.llm_validation?.provider || "auto-classifier",
      original_confidence: Number(article.category_confidence || article.categoryConfidence || 0),
      corrected_labels: labels,
      correction_reason: body.correction_reason || body.correctionReason || null,
      admin_id: admin.id,
      admin_username: admin.username,
      corrected_at: nowIso(),
      feedback_status: "pending",
      feedback_weight: feedbackWeight,
      verified_by: null,
      verified_at: null,
      is_verified: false,
      requires_verification: requiresVerification
    };
    store.records.push(record);
    admin.totalCorrections = Number(admin.totalCorrections || 0) + 1;
  }
  applyCorrectionToArticle(article);
  if (!requiresVerification) processFeedbackRecord(record.id, db);
  logAdmin("article_reclassified", { adminId: admin.id, articleId, recordId: record.id, labels });
  saveState();
  return { success: true, record_id: record.id, article_id: articleId, corrected_labels: labels, message: "Düzeltme kaydedildi ve feedback kuyruğuna eklendi.", requires_verification: requiresVerification, feedback_queued: true, record };
}

function verifyCorrection(req, recordId, body) {
  const admin = getCurrentAdmin(req);
  requirePermission(admin, "can_verify");
  const store = loadState();
  const record = store.records.find((item) => Number(item.id) === Number(recordId));
  if (!record) throw statusError(404, "Düzeltme kaydı bulunamadı.");
  if (Number(record.admin_id) === Number(admin.id)) throw statusError(403, "Admin kendi yaptığı düzeltmeyi doğrulayamaz.");
  if (record.is_verified || record.feedback_status === "processed" || record.feedback_status === "rejected") throw statusError(409, "Bu kayıt zaten doğrulanmış veya sonuçlandırılmış.");
  if (body.approved) {
    record.is_verified = true;
    record.verified_by = admin.id;
    record.verified_at = nowIso();
    record.feedback_status = "processed";
    record.feedback_weight = Number((Number(record.feedback_weight || 1) * 1.3).toFixed(4));
  } else {
    record.feedback_status = "rejected";
  }
  logAdmin("article_reclassification_verified", { adminId: admin.id, recordId: record.id, approved: Boolean(body.approved) });
  saveState();
  return { success: true, record, message: body.approved ? "Düzeltme doğrulandı." : "Düzeltme reddedildi." };
}

function getQueue(status = "pending") {
  const store = loadState();
  return store.records.filter((record) => !status || record.feedback_status === status || (status === "verification" && record.requires_verification && !record.is_verified && record.feedback_status !== "rejected"));
}

function queueStatus() {
  const store = loadState();
  return { pending_count: store.records.filter((r) => r.feedback_status === "pending").length, processed_count: store.records.filter((r) => r.feedback_status === "processed").length, retraining_threshold: RETRAINING_TRIGGERS.count_threshold, next_retraining_at: null, current_batch_id: store.nextBatchId };
}

function feedbackStats() {
  const store = loadState();
  const correctionsPerCategory = Object.fromEntries(ALLOWED_CATEGORIES.map((label) => [label, 0]));
  const confusion = Object.fromEntries(ALLOWED_CATEGORIES.map((label) => [label, {}]));
  for (const record of store.records) {
    for (const label of record.corrected_labels || []) correctionsPerCategory[label] = (correctionsPerCategory[label] || 0) + 1;
    for (const original of record.original_labels || []) {
      for (const corrected of record.corrected_labels || []) {
        if (original !== corrected) confusion[original] = { ...(confusion[original] || {}), [corrected]: ((confusion[original] || {})[corrected] || 0) + 1 };
      }
    }
  }
  const pending = store.records.filter((r) => r.feedback_status === "pending").length;
  const processed = store.records.filter((r) => r.feedback_status === "processed").length;
  return { success: true, queue: queueStatus(), corrections_per_category: correctionsPerCategory, confusion, total_records: store.records.length, pending, processed, dead_letter_count: store.deadLetterQueue.length };
}

function adminStats(adminId) {
  const store = loadState();
  const admin = store.admins.find((item) => Number(item.id) === Number(adminId));
  if (!admin) throw statusError(404, "Admin bulunamadı.");
  const records = store.records.filter((record) => Number(record.admin_id) === Number(adminId));
  const labels = {};
  for (const record of records) for (const label of record.corrected_labels || []) labels[label] = (labels[label] || 0) + 1;
  const most = Object.entries(labels).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
  return { admin_id: admin.id, username: admin.username, total_corrections: records.length, corrections_today: records.filter((r) => String(r.corrected_at).slice(0, 10) === todayKey()).length, accuracy_rate: Number(admin.accuracyRate || 1), most_corrected_category: most, avg_corrections_per_day: records.length };
}

function modelStats() {
  const store = loadState();
  return { success: true, model: store.modelState, training_examples: store.trainingExamples.length, triggers: store.retrainingTriggers.slice(-10) };
}

function checkRetrainingThreshold() {
  const store = loadState();
  if (store.modelState.retrainingRunning) return { should_retrain: false, reason: "zaten çalışıyor" };
  const processed = store.records.filter((r) => r.feedback_status === "processed").length;
  const today = store.records.filter((r) => String(r.corrected_at).slice(0, 10) === todayKey()).length;
  if (processed >= RETRAINING_TRIGGERS.count_threshold) return { should_retrain: true, reason: "threshold" };
  if (today >= RETRAINING_TRIGGERS.daily_rate_threshold) return { should_retrain: true, reason: "daily_rate" };
  if (Number(store.modelState.currentAccuracy) <= RETRAINING_TRIGGERS.accuracy_threshold) return { should_retrain: true, reason: "accuracy_drop" };
  return { should_retrain: false, reason: "not_needed" };
}

function triggerRetraining(req, body = {}) {
  const admin = getCurrentAdmin(req);
  requirePermission(admin, "can_trigger_retrain");
  const store = loadState();
  if (store.modelState.retrainingRunning) throw statusError(409, "Retraining zaten çalışıyor.");
  const trigger = { trigger_id: `rt_${Date.now()}_${crypto.randomBytes(4).toString("hex")}`, trigger_reason: body.reason || "manual", feedback_count: store.records.filter((r) => r.feedback_status === "processed").length, triggered_at: nowIso(), triggered_by: admin.username, status: "queued" };
  store.retrainingTriggers.push(trigger);
  logAdmin("retraining_triggered", { adminId: admin.id, triggerId: trigger.trigger_id });
  saveState();
  return { success: true, trigger };
}

function runRetraining(triggerId) {
  const store = loadState();
  const trigger = store.retrainingTriggers.find((item) => item.trigger_id === triggerId);
  if (!trigger) throw statusError(404, "Retraining tetikleyicisi bulunamadı.");
  store.modelState.retrainingRunning = true;
  trigger.status = "running";
  const oldAccuracy = Number(store.modelState.currentAccuracy || 0.86);
  const processed = store.records.filter((r) => r.feedback_status === "processed");
  const improvement = Math.min(0.04, store.trainingExamples.length / 10000);
  const newAccuracy = Number((oldAccuracy + improvement).toFixed(4));
  if (newAccuracy >= oldAccuracy - ACCURACY_DROP_TOLERANCE) {
    store.modelState.oldVersion = store.modelState.currentVersion;
    store.modelState.oldAccuracy = oldAccuracy;
    store.modelState.currentVersion = trigger.trigger_id;
    store.modelState.currentAccuracy = newAccuracy;
    processed.forEach((record) => { record.feedback_status = "used_in_training"; });
    trigger.status = "completed";
  } else {
    trigger.status = "failed";
  }
  store.modelState.retrainingRunning = false;
  saveState();
  return { success: trigger.status === "completed", trigger, model: store.modelState };
}

function getConfig() {
  return { allowedCategories: ALLOWED_CATEGORIES, numCategories: ALLOWED_CATEGORIES.length, roles: ROLE_PERMISSIONS, retrainingTriggers: RETRAINING_TRIGGERS, accuracyDropTolerance: ACCURACY_DROP_TOLERANCE, rateLimitPerMinute: RATE_LIMIT_PER_MINUTE };
}

function buildFeedCorrectionStats(articles = []) {
  const corrected = articles.filter((article) => article.is_admin_corrected || article.isAdminCorrected).length;
  return { corrected_articles: corrected, total_articles: articles.length, queue: queueStatus(), model: loadState().modelState };
}

function resetForTests() {
  persistEnabled = false;
  state = defaultState();
  rateLimits.clear();
  return state;
}

module.exports = {
  ALLOWED_CATEGORIES,
  ROLE_PERMISSIONS,
  RETRAINING_TRIGGERS,
  hashPassword,
  verifyPassword,
  signToken,
  verifyToken,
  login,
  logout,
  refresh,
  getCurrentAdmin,
  validateLabels,
  reclassify,
  verifyCorrection,
  getQueue,
  queueStatus,
  feedbackStats,
  adminStats,
  modelStats,
  checkRetrainingThreshold,
  triggerRetraining,
  runRetraining,
  processFeedbackRecord,
  applyCorrectionToArticle,
  applyCorrectionToCluster,
  buildFeedCorrectionStats,
  getConfig,
  _internal: { resetForTests, loadState, saveState, statusError, findArticle, latestRecordForArticle, rateLimits }
};
