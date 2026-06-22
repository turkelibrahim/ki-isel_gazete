import { loadAnalyticsDashboard } from "../utils/recommendationApi.js";

function escapeHtml(value = "") {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
}

function barRows(items = [], labelKey, valueKey = "count") {
  const max = Math.max(1, ...items.map((item) => Number(item[valueKey] || 0)));
  return items.map((item) => {
    const label = item[labelKey] || "Bilinmiyor";
    const value = Number(item[valueKey] || 0);
    const width = Math.max(3, Math.round((value / max) * 100));
    return `<div class="analytics-bar-row"><span>${escapeHtml(label)}</span><div><i style="width:${width}%"></i></div><b>${escapeHtml(value)}</b></div>`;
  }).join("");
}

function weeklyRows(items = []) {
  const max = Math.max(1, ...items.map((item) => Number(item.reading_time_minutes || 0)));
  return items.map((item) => {
    const value = Number(item.reading_time_minutes || 0);
    const height = Math.max(8, Math.round((value / max) * 110));
    return `<div class="analytics-column"><i style="height:${height}px"></i><span>${escapeHtml((item.date || "").slice(5))}</span><b>${value} dk</b></div>`;
  }).join("");
}

export function initUserDashboard({ showToast } = {}) {
  const root = document.getElementById("analytics-dashboard-root");
  if (!root) return null;

  async function load() {
    root.innerHTML = `<div class="analytics-state"><i class="fa-solid fa-spinner fa-spin"></i><span>Dashboard hazırlanıyor...</span></div>`;
    try {
      const data = await loadAnalyticsDashboard();
      if (data.empty) {
        root.innerHTML = `<div class="analytics-state"><i class="fa-regular fa-chart-bar"></i><strong>Henüz yeterli okuma veriniz yok</strong><p>${escapeHtml(data.message || "Haber okudukça istatistikleriniz burada görünecek.")}</p></div>`;
        return;
      }
      const s = data.summary || {};
      root.innerHTML = `
        <div class="analytics-dashboard-header">
          <div><p class="kicker"><i class="fa-solid fa-chart-pie"></i> Okuma analitiği</p><h2>Kişisel Dashboard</h2></div>
          <button type="button" id="analytics-refresh"><i class="fa-solid fa-rotate"></i> Yenile</button>
        </div>
        <div class="analytics-summary-grid">
          <div><span>Okunan haber</span><strong>${escapeHtml(s.total_articles_read || 0)}</strong></div>
          <div><span>Toplam süre</span><strong>${escapeHtml(s.total_reading_time_minutes || 0)} dk</strong></div>
          <div><span>Bu hafta</span><strong>${escapeHtml(s.weekly_reading_time_minutes || 0)} dk</strong></div>
          <div><span>Öneri CTR</span><strong>${escapeHtml(s.recommendation_ctr || 0)}%</strong></div>
        </div>
        <div class="analytics-grid">
          <section class="analytics-panel"><h3>En çok ilgilenilen kategoriler</h3>${barRows(data.top_categories || [], "category") || "<p>Veri yok.</p>"}</section>
          <section class="analytics-panel"><h3>En çok okunan kaynaklar</h3>${barRows(data.top_sources || [], "source_name") || "<p>Veri yok.</p>"}</section>
          <section class="analytics-panel analytics-panel-wide"><h3>Haftalık okuma süresi</h3><div class="analytics-weekly-chart">${weeklyRows(data.weekly_reading || []) || "<p>Veri yok.</p>"}</div></section>
          <section class="analytics-panel analytics-panel-wide"><h3>Son okunan haberler</h3><div class="analytics-recent-list">${(data.recent_articles || []).slice(0, 8).map((item) => `<button type="button" data-article-id="${escapeHtml(item.id)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.category || "Genel")} · ${escapeHtml(item.source_name || "Kaynak")}</span></button>`).join("") || "<p>Veri yok.</p>"}</div></section>
        </div>`;
      root.querySelector("#analytics-refresh")?.addEventListener("click", load);
      root.querySelectorAll("[data-article-id]").forEach((button) => button.addEventListener("click", () => window.showDetail?.(button.dataset.articleId)));
    } catch (error) {
      root.innerHTML = `<div class="analytics-state error"><i class="fa-solid fa-triangle-exclamation"></i><strong>Dashboard yüklenemedi</strong><p>${escapeHtml(error.message || "Beklenmeyen hata")}</p></div>`;
    }
  }

  return { load };
}
