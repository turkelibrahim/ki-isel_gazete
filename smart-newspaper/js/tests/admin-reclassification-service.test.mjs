
import assert from "node:assert/strict";
import test from "node:test";

import AdminService from "../../services/adminReclassificationService.js";

function authReq(token) {
  return { headers: { authorization: `Bearer ${token}` } };
}

function dbWithArticle(id = "news_1") {
  return { articles: [{ id, title: "Yapay zeka çipi üretiminde rekor", summary: "Yapay zeka yatırımı borsayı etkiledi", labels: ["Teknoloji"], category: "Teknoloji", category_confidence: 0.7 }] };
}

test("valid reviewer correction is queued and applied to feed article", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("reviewer", "admin123");
  const db = dbWithArticle();
  const result = AdminService.reclassify(authReq(login.token), { article_id: "news_1", corrected_labels: ["Teknoloji", "Ekonomi"], correction_reason: "Ekonomi etkisi var" }, db);
  assert.equal(result.success, true);
  assert.equal(result.feedback_queued, true);
  assert.deepEqual(db.articles[0].labels, ["Teknoloji", "Ekonomi"]);
  assert.equal(db.articles[0].is_admin_corrected, true);
});

test("invalid category returns 422-style error and no record is saved", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("reviewer", "admin123");
  assert.throws(() => AdminService.reclassify(authReq(login.token), { article_id: "news_1", corrected_labels: ["Gündem"] }, dbWithArticle()), /Geçersiz kategori/);
  assert.equal(AdminService._internal.loadState().records.length, 0);
});

test("same admin same article updates existing record", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("editor", "admin123");
  const db = dbWithArticle();
  const first = AdminService.reclassify(authReq(login.token), { article_id: "news_1", corrected_labels: ["Teknoloji"] }, db);
  const second = AdminService.reclassify(authReq(login.token), { article_id: "news_1", corrected_labels: ["Teknoloji", "Ekonomi"] }, db);
  assert.equal(first.record_id, second.record_id);
  assert.equal(AdminService._internal.loadState().records.length, 1);
});

test("admin cannot verify own correction", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("editor", "admin123");
  const db = dbWithArticle();
  const result = AdminService.reclassify(authReq(login.token), { article_id: "news_1", corrected_labels: ["Ekonomi"] }, db);
  assert.throws(() => AdminService.verifyCorrection(authReq(login.token), result.record_id, { approved: true }), /kendi yaptığı/);
});

test("five failed logins lock the admin account", () => {
  AdminService._internal.resetForTests();
  for (let i = 0; i < 4; i += 1) assert.throws(() => AdminService.login("reviewer", "bad"), /hatalı/);
  assert.throws(() => AdminService.login("reviewer", "bad"), /Hesap kilitlendi/);
});

test("rate limit rejects the 61st reclassification in a minute", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("superadmin", "admin123");
  const db = { articles: [] };
  for (let i = 0; i < 60; i += 1) {
    db.articles.push({ id: `n${i}`, title: "Spor", labels: ["Spor"], category: "Spor" });
    AdminService.reclassify(authReq(login.token), { article_id: `n${i}`, corrected_labels: ["Spor"] }, db);
  }
  db.articles.push({ id: "n61", title: "Spor", labels: ["Spor"], category: "Spor" });
  assert.throws(() => AdminService.reclassify(authReq(login.token), { article_id: "n61", corrected_labels: ["Spor"] }, db), /Çok fazla istek/);
});

test("100 processed corrections trigger retraining threshold", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("editor", "admin123");
  const db = { articles: [] };
  for (let i = 0; i < 100; i += 1) {
    db.articles.push({ id: `n${i}`, title: "Ekonomi", labels: ["Ekonomi"], category: "Ekonomi" });
    AdminService._internal.rateLimits.clear();
    const result = AdminService.reclassify(authReq(login.token), { article_id: `n${i}`, corrected_labels: ["Ekonomi"] }, db);
    const record = AdminService._internal.loadState().records.find((item) => item.id === result.record_id);
    record.feedback_status = "processed";
  }
  assert.deepEqual(AdminService.checkRetrainingThreshold(), { should_retrain: true, reason: "threshold" });
});

test("correction payload can be applied later to feed article", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("editor", "admin123");
  const db = dbWithArticle("late_1");
  AdminService.reclassify(authReq(login.token), { article_id: "late_1", corrected_labels: ["Bilim"] }, db);
  const article = { id: "late_1", title: "Uzay araştırması", labels: ["Teknoloji"], category: "Teknoloji" };
  AdminService.applyCorrectionToArticle(article);
  assert.equal(article.category, "Bilim");
  assert.equal(article.admin_correction.feedback_status, "processed");
});

test("retraining run deploys safe model and marks feedback used", () => {
  AdminService._internal.resetForTests();
  const login = AdminService.login("superadmin", "admin123");
  const trigger = AdminService.triggerRetraining(authReq(login.token), { reason: "manual" }).trigger;
  const result = AdminService.runRetraining(trigger.trigger_id);
  assert.equal(result.success, true);
  assert.equal(result.trigger.status, "completed");
});
