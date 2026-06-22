"use strict";

const fs = require("fs");
const zlib = require("zlib");
const { safeReportPath, fileUrl, sanitizeFilePart, escapeXml } = require("./reportExportUtils");

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) c = ((c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1));
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i += 1) crc = CRC_TABLE[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
function dosTimeDate(date = new Date()) {
  const time = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
  const dosDate = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
  return { time, date: dosDate };
}
function zipStore(files) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  const now = dosTimeDate();
  for (const file of files) {
    const name = Buffer.from(file.name, "utf8");
    const data = Buffer.isBuffer(file.data) ? file.data : Buffer.from(String(file.data), "utf8");
    const crc = crc32(data);
    const local = Buffer.alloc(30 + name.length);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0, 6); local.writeUInt16LE(0, 8);
    local.writeUInt16LE(now.time, 10); local.writeUInt16LE(now.date, 12); local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18); local.writeUInt32LE(data.length, 22); local.writeUInt16LE(name.length, 26); local.writeUInt16LE(0, 28); name.copy(local, 30);
    locals.push(local, data);
    const central = Buffer.alloc(46 + name.length);
    central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6); central.writeUInt16LE(0, 8); central.writeUInt16LE(0, 10);
    central.writeUInt16LE(now.time, 12); central.writeUInt16LE(now.date, 14); central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20); central.writeUInt32LE(data.length, 24); central.writeUInt16LE(name.length, 28); central.writeUInt16LE(0, 30); central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34); central.writeUInt16LE(0, 36); central.writeUInt32LE(0, 38); central.writeUInt32LE(offset, 42); name.copy(central, 46);
    centrals.push(central);
    offset += local.length + data.length;
  }
  const centralOffset = offset;
  const centralSize = centrals.reduce((sum, b) => sum + b.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(0, 4); end.writeUInt16LE(0, 6); end.writeUInt16LE(files.length, 8); end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(centralSize, 12); end.writeUInt32LE(centralOffset, 16); end.writeUInt16LE(0, 20);
  return Buffer.concat([...locals, ...centrals, end]);
}
function colName(index) { let n = index + 1; let s = ""; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }
function cellXml(value, r) {
  if (typeof value === "number" && Number.isFinite(value)) return `<c r="${r}"><v>${value}</v></c>`;
  return `<c r="${r}" t="inlineStr"><is><t>${escapeXml(value ?? "")}</t></is></c>`;
}
function sheetXml(rows = []) {
  const safeRows = rows.length ? rows : [["Veri yok", "Seçilen tarih aralığı için kayıt bulunamadı."]];
  const body = safeRows.map((row, ri) => `<row r="${ri + 1}">${row.map((v, ci) => cellXml(v, `${colName(ci)}${ri + 1}`)).join("")}</row>`).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`;
}
function workbookXml(sheets) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map((s, i) => `<sheet name="${escapeXml(s.name).slice(0, 31)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")}</sheets></workbook>`;
}
function workbookRels(sheets) { return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((s, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("")}</Relationships>`; }
function contentTypes(sheets) { return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${sheets.map((s, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")}</Types>`; }
function rootRels() { return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`; }

function makeSheets(reportData) {
  const s = reportData.summary || {};
  return [
    { name: "Özet", rows: [["Metrik", "Değer"], ["Günlük Aktif Kullanıcı", s.daily_active_users || 0], ["Toplam Etkileşim", s.total_interactions || 0], ["Toplam Okunma", s.total_reads || 0], ["Toplam Paylaşım", s.total_shares || 0], ["Ortalama Okuma Süresi (sn)", s.average_reading_time_seconds || 0]] },
    { name: "Günlük Aktif Kullanıcılar", rows: [["Tarih", "Aktif Kullanıcı"], ...(reportData.daily_active_users || []).map((r) => [r.date, r.active_users])] },
    { name: "En Çok Okunan Haberler", rows: [["Başlık", "Kategori", "Kaynak", "Okunma", "Paylaşım", "Ort. Okuma Süresi"], ...(reportData.top_news || []).map((r) => [r.title, r.category, r.source_name, r.read_count, r.share_count, r.average_reading_time_seconds])] },
    { name: "Kategori Trafiği", rows: [["Kategori", "Görüntülenme", "Okuma Süresi", "Oran %", "En Popüler Haber"], ...(reportData.category_traffic || []).map((r) => [r.category, r.views, r.reading_time_seconds, r.percentage, r.top_news_title])] },
    { name: "Sistem Metrikleri", rows: [["Tarih", "CPU %", "RAM %", "Request", "Error", "Avg Response", "PDF", "Email", "Report", "Scheduler"], ...(reportData.system_metrics || []).map((r) => [r.created_at, r.cpu_usage, r.memory_usage, r.request_count, r.error_count, r.average_response_time, r.pdf_generation_count, r.email_sent_count, r.report_generation_count, r.scheduler_status])] }
  ];
}
function generateExcelReport(reportData, reportRecord) {
  const sheets = makeSheets(reportData);
  const files = [
    { name: "[Content_Types].xml", data: contentTypes(sheets) },
    { name: "_rels/.rels", data: rootRels() },
    { name: "xl/workbook.xml", data: workbookXml(sheets) },
    { name: "xl/_rels/workbook.xml.rels", data: workbookRels(sheets) },
    ...sheets.map((sheet, i) => ({ name: `xl/worksheets/sheet${i + 1}.xml`, data: sheetXml(sheet.rows) }))
  ];
  const fileName = `report-${sanitizeFilePart(reportRecord.id)}-${sanitizeFilePart(reportRecord.report_type)}-${Date.now()}.xlsx`;
  const outputPath = safeReportPath(fileName);
  fs.writeFileSync(outputPath, zipStore(files));
  return { path: outputPath, url: fileUrl(fileName), fileName };
}
module.exports = { generateExcelReport, makeSheets };
