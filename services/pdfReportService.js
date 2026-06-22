"use strict";

const fs = require("fs");
const { safeReportPath, fileUrl, sanitizeFilePart } = require("./reportExportUtils");

function escapePdfText(value = "") { return String(value ?? "").replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)").replace(/[\r\n]+/g, " "); }
function buildLines(reportData = {}) {
  const summary = reportData.summary || {};
  const lines = [
    "SmartNewspaper Kullanım Raporu",
    `Tarih Aralığı: ${reportData.date_range_start || ""} - ${reportData.date_range_end || ""}`,
    `Rapor Türü: ${reportData.report_type || "full_admin_report"}`,
    "",
    `Günlük Aktif Kullanıcı: ${summary.daily_active_users || 0}`,
    `Toplam Etkileşim: ${summary.total_interactions || 0}`,
    `Toplam Okunma: ${summary.total_reads || 0}`,
    `Toplam Paylaşım: ${summary.total_shares || 0}`,
    `Ortalama Okuma Süresi: ${summary.average_reading_time_seconds || 0} sn`,
    "",
    "En Çok Okunan Haberler"
  ];
  for (const item of (reportData.top_news || []).slice(0, 12)) lines.push(`- ${item.title} | ${item.category} | ${item.read_count} okuma`);
  lines.push("", "Kategori Trafiği");
  for (const item of (reportData.category_traffic || []).slice(0, 12)) lines.push(`- ${item.category}: ${item.views} görüntülenme, %${item.percentage}`);
  lines.push("", "Sistem Metrikleri");
  for (const item of (reportData.system_metrics || []).slice(-8)) lines.push(`- ${item.created_at}: CPU ${item.cpu_usage}%, RAM ${item.memory_usage}%, Req ${item.request_count}, Err ${item.error_count}`);
  return lines;
}
function createSimplePdf(lines) {
  const objects = [];
  const add = (s) => { objects.push(s); return objects.length; };
  const fontId = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  const content = ["BT", "/F1 12 Tf", "50 790 Td"];
  lines.forEach((line, index) => {
    if (index > 0) content.push("0 -18 Td");
    content.push(`(${escapePdfText(line).slice(0, 130)}) Tj`);
  });
  content.push("ET");
  const stream = content.join("\n");
  const contentId = add(`<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`);
  const pageId = add(`<< /Type /Page /Parent 4 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 ${fontId} 0 R >> >> /Contents ${contentId} 0 R >>`);
  const pagesId = add(`<< /Type /Pages /Kids [${pageId} 0 R] /Count 1 >>`);
  const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`);
  let out = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((obj, i) => { offsets[i + 1] = Buffer.byteLength(out); out += `${i + 1} 0 obj\n${obj}\nendobj\n`; });
  const xref = Buffer.byteLength(out);
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i <= objects.length; i += 1) out += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(out, "utf8");
}
function generatePdfReport(reportData, reportRecord) {
  const fileName = `report-${sanitizeFilePart(reportRecord.id)}-${sanitizeFilePart(reportRecord.report_type)}-${Date.now()}.pdf`;
  const outputPath = safeReportPath(fileName);
  fs.writeFileSync(outputPath, createSimplePdf(buildLines(reportData)));
  return { path: outputPath, url: fileUrl(fileName), fileName };
}
module.exports = { generatePdfReport, buildLines, createSimplePdf };
