"use strict";

const fs = require("fs");
const path = require("path");

let nodemailer = null;
try { nodemailer = require("nodemailer"); } catch { nodemailer = null; }

const TEMPLATE_DIR = path.join(__dirname, "..", "templates", "email");

function escapeHtml(value = "") {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
}

function stripHtml(value = "") {
  return String(value || "").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function loadTemplate(name) {
  const file = path.join(TEMPLATE_DIR, `${name}.html`);
  if (!fs.existsSync(file)) return "";
  return fs.readFileSync(file, "utf8");
}

function renderEmailTemplate(notification = {}, options = {}) {
  const type = notification.notification_type || notification.type || "critical_announcement";
  const templateName = type.includes("event") || type.includes("hour") || type.includes("day") ? "event-reminder" : "critical-announcement";
  const base = loadTemplate(templateName) || `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{{title}}</title></head><body><h1>{{title}}</h1><p>{{message}}</p><a href="{{detailUrl}}">Detayları Gör</a></body></html>`;
  const replacements = {
    title: escapeHtml(notification.title || "SmartNewspaper Bildirimi"),
    message: escapeHtml(notification.message || ""),
    eventDate: escapeHtml(notification.event_date || notification.eventDate || notification.scheduled_at || "Tarih belirtilmedi"),
    remainingTime: escapeHtml(options.remainingTime || "Yaklaşıyor"),
    detailUrl: escapeHtml(notification.target_url || notification.targetUrl || "/"),
    preferencesUrl: escapeHtml(options.preferencesUrl || "/#notifications")
  };
  return base.replace(/{{\s*(\w+)\s*}}/g, (_, key) => replacements[key] ?? "");
}

function getSmtpConfig() {
  return {
    host: process.env.SMTP_HOST || "",
    port: Number(process.env.SMTP_PORT || 587),
    user: process.env.SMTP_USER || "",
    pass: process.env.SMTP_PASSWORD || "",
    from: process.env.SMTP_FROM || process.env.SENDGRID_FROM_EMAIL || process.env.MAILGUN_FROM_EMAIL || ""
  };
}

async function sendEmailNotification(notification = {}, context = {}) {
  const user = context.user || {};
  if (!user.email) throw new Error("Kullanıcı e-posta adresi bulunamadı.");
  const html = renderEmailTemplate(notification, context);
  const text = stripHtml(html);
  const cfg = getSmtpConfig();
  if (!cfg.host || !cfg.from) {
    throw new Error("SMTP bilgileri eksik; e-posta kanalı devre dışı.");
  }
  if (!nodemailer) {
    throw new Error("nodemailer paketi kurulu değil; e-posta gönderimi yapılamadı.");
  }
  const transporter = nodemailer.createTransport({
    host: cfg.host,
    port: cfg.port,
    secure: cfg.port === 465,
    auth: cfg.user ? { user: cfg.user, pass: cfg.pass } : undefined
  });
  await transporter.sendMail({
    to: user.email,
    from: cfg.from,
    subject: notification.title || "SmartNewspaper Bildirimi",
    html,
    text
  });
  return { success: true, provider: "smtp" };
}

module.exports = { escapeHtml, stripHtml, renderEmailTemplate, sendEmailNotification, getSmtpConfig };
