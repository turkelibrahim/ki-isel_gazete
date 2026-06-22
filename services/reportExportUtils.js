"use strict";
const fs = require("fs");
const path = require("path");
function ensureDir(dir) { if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }); }
function sanitizeFilePart(value = "") { return String(value || "file").replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "file"; }
function reportDir() { const dir = path.resolve(process.cwd(), process.env.REPORT_STORAGE_DIR || "generated-reports"); ensureDir(dir); return dir; }
function safeReportPath(fileName) { const dir = reportDir(); const target = path.resolve(dir, sanitizeFilePart(fileName)); if (!target.startsWith(dir)) throw new Error("Geçersiz dosya yolu."); return target; }
function fileUrl(fileName) { return `/generated-reports/${sanitizeFilePart(fileName)}`; }
function escapeXml(value = "") { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&apos;"}[ch])); }
function escapeHtml(value = "") { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch])); }
module.exports = { ensureDir, sanitizeFilePart, safeReportPath, fileUrl, escapeXml, escapeHtml, reportDir };
