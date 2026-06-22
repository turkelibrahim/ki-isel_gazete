import { fetchUsageReport, exportReport, fetchGeneratedReports } from '../utils/adminReportApi.js';
import { escapeHtml } from '../utils/textUtils.js';

function today(offset = 0) { const d = new Date(); d.setDate(d.getDate() + offset); return d.toISOString().slice(0, 10); }
function fmt(n) { return Number(n || 0).toLocaleString('tr-TR'); }
function table(rows, cols) {
  if (!rows.length) return '<p class="admin-empty">Seçilen tarih aralığı için rapor verisi bulunamadı.</p>';
  return `<table class="admin-report-table"><thead><tr>${cols.map(c => `<th>${escapeHtml(c.label)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${cols.map(c => `<td>${escapeHtml(row[c.key] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
export function initAdminReportsPage(rootId = 'admin-reports-root') {
  const root = document.getElementById(rootId);
  if (!root) return null;
  const state = { reportType: 'full_admin_report', startDate: today(-7), endDate: today(0), data: null, loading: false, error: '' };
  async function load() {
    state.loading = true; render();
    try { const data = await fetchUsageReport(state); if (!data.success) throw new Error(data.message || 'Rapor alınamadı.'); state.data = data; state.error = ''; }
    catch (e) { state.error = e.message || String(e); }
    finally { state.loading = false; render(); }
  }
  async function doExport(format) {
    const btnText = format === 'excel' ? 'Excel' : 'PDF';
    root.querySelector('[data-report-status]').textContent = `${btnText} oluşturuluyor...`;
    const data = await exportReport(format, state);
    root.querySelector('[data-report-status]').textContent = data.success ? `${btnText} raporu oluşturuldu.` : (data.message || `${btnText} oluşturulamadı.`);
    await loadGenerated();
  }
  async function loadGenerated() {
    const box = root.querySelector('[data-generated-reports]'); if (!box) return;
    const data = await fetchGeneratedReports();
    const rows = data.data || [];
    box.innerHTML = rows.length ? rows.slice(0, 8).map(r => `<a class="generated-report-row" href="/api/admin/reports/${encodeURIComponent(r.id)}/download"><strong>${escapeHtml(r.title || r.report_type)}</strong><span>${escapeHtml(r.format)} · ${escapeHtml(r.status)}</span></a>`).join('') : '<p class="admin-empty">Henüz oluşturulmuş rapor yok.</p>';
  }
  function render() {
    const d = state.data || {};
    const s = d.summary || {};
    root.innerHTML = `<section class="admin-module-page"><div class="admin-module-head"><div><p class="kicker">Admin Raporları</p><h2>Kullanım Raporları</h2><small>Gerçek analitik, haber ve sistem metriklerinden hesaplanır.</small></div><span class="admin-permission-badge">reports.view</span></div><div class="report-filter-grid"><label>Rapor türü<select data-report-type><option value="full_admin_report">Tam Admin Raporu</option><option value="usage_summary">Özet</option><option value="active_users">Aktif Kullanıcılar</option><option value="top_news">En Çok Okunan</option><option value="category_traffic">Kategori Trafiği</option><option value="system_metrics">Sistem Metrikleri</option></select></label><label>Başlangıç<input type="date" data-start value="${escapeHtml(state.startDate)}"></label><label>Bitiş<input type="date" data-end value="${escapeHtml(state.endDate)}"></label><button type="button" data-load-report>Raporu Getir</button></div>${state.loading ? '<p class="admin-loading">Rapor yükleniyor...</p>' : ''}${state.error ? `<p class="admin-error">${escapeHtml(state.error)}</p>` : ''}<div class="admin-summary-grid"><article><span>Aktif Kullanıcı</span><strong>${fmt(s.daily_active_users)}</strong></article><article><span>Etkileşim</span><strong>${fmt(s.total_interactions)}</strong></article><article><span>Okunma</span><strong>${fmt(s.total_reads)}</strong></article><article><span>Paylaşım</span><strong>${fmt(s.total_shares)}</strong></article></div><div class="report-actions"><button type="button" data-export="excel">Excel Dışa Aktar</button><button type="button" data-export="pdf">PDF Dışa Aktar</button><span data-report-status></span></div><div class="admin-report-grid"><section><h3>En Çok Okunan Haberler</h3>${table(d.top_news || [], [{key:'title',label:'Haber'}, {key:'category',label:'Kategori'}, {key:'source_name',label:'Kaynak'}, {key:'read_count',label:'Okunma'}])}</section><section><h3>Kategori Trafiği</h3>${table(d.category_traffic || [], [{key:'category',label:'Kategori'}, {key:'views',label:'Görüntülenme'}, {key:'percentage',label:'Oran %'}])}</section></div><section><h3>Oluşturulmuş Raporlar</h3><div data-generated-reports></div></section></section>`;
    root.querySelector('[data-report-type]').value = state.reportType;
    root.querySelector('[data-load-report]')?.addEventListener('click', () => { state.reportType = root.querySelector('[data-report-type]').value; state.startDate = root.querySelector('[data-start]').value; state.endDate = root.querySelector('[data-end]').value; load(); });
    root.querySelectorAll('[data-export]').forEach(btn => btn.addEventListener('click', () => doExport(btn.dataset.export)));
    loadGenerated();
  }
  render(); load(); return { load };
}
