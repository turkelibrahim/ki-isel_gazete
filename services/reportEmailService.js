"use strict";
const nodemailer = (() => { try { return require("nodemailer"); } catch { return null; } })();
function html(report) { return `<!doctype html><html lang="tr"><meta charset="utf-8"><body style="font-family:Arial,sans-serif;background:#f5f2ea;padding:24px"><div style="max-width:640px;margin:auto;background:white;border-radius:16px;padding:24px"><h1>SmartNewspaper Raporu</h1><p>${report.title || report.report_type} hazırlandı.</p><p><strong>Tarih:</strong> ${report.date_range_start || ""} - ${report.date_range_end || ""}</p><p><a href="${report.file_url || "#"}" style="background:#111;color:#fff;padding:12px 18px;border-radius:10px;text-decoration:none">Raporu indir</a></p></div></body></html>`; }
async function sendReportEmail(recipients = [], report = {}) {
  const list = Array.isArray(recipients) ? recipients.filter(Boolean) : String(recipients || "").split(/[;,]/).map((x) => x.trim()).filter(Boolean);
  if (!list.length) return { success: true, skipped: true, reason: "recipient_empty" };
  if (!process.env.SMTP_HOST || !process.env.SMTP_FROM || !nodemailer) return { success: false, skipped: true, error: "SMTP yapılandırması yok." };
  const transporter = nodemailer.createTransport({ host: process.env.SMTP_HOST, port: Number(process.env.SMTP_PORT || 587), secure: Number(process.env.SMTP_PORT) === 465, auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD || "" } : undefined });
  await transporter.sendMail({ from: process.env.SMTP_FROM, to: list.join(","), subject: `SmartNewspaper Raporu - ${report.title || report.report_type}`, html: html(report), text: `SmartNewspaper raporu hazırlandı: ${report.file_url || ""}` });
  return { success: true, sent: list.length };
}
module.exports = { sendReportEmail, renderReportEmailTemplate: html };
