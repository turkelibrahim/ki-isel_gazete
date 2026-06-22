import { escapeHtml } from "../utils/textUtils.js";
import { debounce } from "../utils/searchFilters.js";
import { searchNews, fetchSearchSources, fetchSearchSuggestions, fetchTrends, trackSearchClick } from "../utils/searchApi.js";

const DEFAULT_STATE = {
  q: "",
  category: "",
  source: "",
  dateFilter: "",
  startDate: "",
  endDate: "",
  sort: "relevance",
  page: 1,
  limit: 20
};

function fmtDate(value) {
  if (!value) return "Tarih yok";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Tarih yok";
  return new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

function articleUrl(article = {}) {
  return article.url || article.sourceUrl || article.source_url || "#";
}

function renderSearchCard(article = {}) {
  const labels = Array.isArray(article.labels) ? article.labels.slice(0, 3) : [];
  const sources = Array.isArray(article.sources) ? article.sources : [];
  const sourceNames = sources.map((s) => s.sourceName || s.source_name || s.source).filter(Boolean).slice(0, 5);
  return `
    <article class="search-result-card" data-search-article-id="${escapeHtml(article.id || "")}">
      <div class="search-result-image ${article.image_url || article.imageUrl ? "" : "is-placeholder"}">
        ${article.image_url || article.imageUrl ? `<img src="${escapeHtml(article.image_url || article.imageUrl)}" alt="" loading="lazy" />` : `<span>SmartNewspaper</span>`}
      </div>
      <div class="search-result-body">
        <div class="search-result-meta">
          <span>${escapeHtml(article.source_name || article.sourceName || "Kaynak belirtilmedi")}</span>
          <span>${escapeHtml(fmtDate(article.published_at || article.publishedAt))}</span>
          ${article.trend_score ? `<span>Trend ${Math.round(article.trend_score)}</span>` : ""}
          ${article.score ? `<span>Skor ${Math.round(article.score)}</span>` : ""}
        </div>
        <h3><a href="${escapeHtml(articleUrl(article))}" target="_blank" rel="noopener">${escapeHtml(article.title || "Başlıksız haber")}</a></h3>
        <p>${escapeHtml(article.summary || article.description || "Özet bulunamadı.")}</p>
        <div class="search-result-badges">
          ${labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}
          ${(sourceNames.length ? sourceNames : [article.source_name || article.sourceName].filter(Boolean)).map((name) => `<em>${escapeHtml(name)}</em>`).join("")}
        </div>
      </div>
    </article>`;
}

function renderTrendCard(article = {}) {
  return `
    <button class="trend-search-card" data-search-article-id="${escapeHtml(article.id || "")}" type="button">
      <strong>${escapeHtml(article.title || "Trend haber")}</strong>
      <span>${escapeHtml(article.source_name || article.sourceName || "Kaynak")}</span>
      <small>Trend skoru: ${Math.round(Number(article.trend_score || 0))}</small>
    </button>`;
}

export function initSearchPanel(options = {}) {
  const root = document.getElementById("advanced-search-root");
  if (!root) return null;
  const state = { ...DEFAULT_STATE };
  const toast = typeof options.showToast === "function" ? options.showToast : () => {};

  root.innerHTML = `
    <section class="advanced-search-panel">
      <div class="advanced-search-hero">
        <div>
          <p class="kicker">Gelişmiş Arama</p>
          <h2>Haberleri full-text arama ve trend skoruyla keşfet</h2>
          <p>Başlık, özet, içerik, etiket ve kaynak alanlarında Türkçe karakter uyumlu arama yap.</p>
        </div>
        <div class="advanced-search-input-wrap">
          <input id="advanced-search-input" type="search" maxlength="150" placeholder="Ekonomi, deprem, teknoloji, kaynak adı…" autocomplete="off" />
          <button id="advanced-search-submit" type="button"><i class="fa-solid fa-magnifying-glass"></i> Ara</button>
          <div id="advanced-search-suggestions" class="advanced-search-suggestions" hidden></div>
        </div>
      </div>

      <div class="advanced-search-filters">
        <label>Kategori
          <select id="advanced-search-category">
            <option value="">Tümü</option>
            <option value="gundem">Gündem</option>
            <option value="politika">Politika</option>
            <option value="magazin">Magazin</option>
            <option value="teknoloji">Teknoloji</option>
            <option value="spor">Spor</option>
            <option value="saglik">Sağlık</option>
            <option value="ekonomi">Ekonomi</option>
            <option value="dünya">Dünya</option>
          </select>
        </label>
        <label>Kaynak
          <select id="advanced-search-source"><option value="">Tüm kaynaklar</option></select>
        </label>
        <label>Tarih
          <select id="advanced-search-date">
            <option value="">Tümü</option>
            <option value="today">Bugün</option>
            <option value="this_week">Bu hafta</option>
            <option value="this_month">Bu ay</option>
          </select>
        </label>
        <label>Başlangıç <input id="advanced-search-start" type="date" /></label>
        <label>Bitiş <input id="advanced-search-end" type="date" /></label>
        <label>Sıralama
          <select id="advanced-search-sort">
            <option value="relevance">Alaka düzeyi</option>
            <option value="newest">En yeni</option>
            <option value="most_read">En çok okunan</option>
            <option value="most_shared">En çok paylaşılan</option>
            <option value="trend">Trend</option>
          </select>
        </label>
        <button id="advanced-search-clear" type="button">Filtreleri temizle</button>
      </div>

      <section class="advanced-trends-section">
        <div class="section-heading"><div><p class="kicker">Trendler</p><h3>Son 24 saatte yükselen haberler</h3></div></div>
        <div id="advanced-trends-list" class="advanced-trends-list"><p>Trendler yükleniyor...</p></div>
      </section>

      <div class="advanced-search-status" id="advanced-search-status" aria-live="polite"></div>
      <div id="advanced-search-results" class="advanced-search-results"></div>
      <div class="advanced-search-pagination">
        <button id="advanced-search-prev" type="button">Önceki</button>
        <span id="advanced-search-page">1</span>
        <button id="advanced-search-next" type="button">Sonraki</button>
      </div>
    </section>`;

  const els = {
    input: root.querySelector("#advanced-search-input"),
    submit: root.querySelector("#advanced-search-submit"),
    suggestions: root.querySelector("#advanced-search-suggestions"),
    category: root.querySelector("#advanced-search-category"),
    source: root.querySelector("#advanced-search-source"),
    date: root.querySelector("#advanced-search-date"),
    start: root.querySelector("#advanced-search-start"),
    end: root.querySelector("#advanced-search-end"),
    sort: root.querySelector("#advanced-search-sort"),
    clear: root.querySelector("#advanced-search-clear"),
    status: root.querySelector("#advanced-search-status"),
    results: root.querySelector("#advanced-search-results"),
    trends: root.querySelector("#advanced-trends-list"),
    prev: root.querySelector("#advanced-search-prev"),
    next: root.querySelector("#advanced-search-next"),
    page: root.querySelector("#advanced-search-page")
  };

  async function loadSources() {
    const payload = await fetchSearchSources();
    const sources = Array.isArray(payload.data) ? payload.data : [];
    els.source.innerHTML = `<option value="">Tüm kaynaklar</option>${sources.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("")}`;
  }

  async function loadTrends() {
    try {
      const payload = await fetchTrends({ limit: 8, category: state.category, source: state.source, dateFilter: state.dateFilter });
      const trends = Array.isArray(payload.data) ? payload.data : [];
      els.trends.innerHTML = trends.length ? trends.map(renderTrendCard).join("") : `<p>Şu an trend haber bulunamadı.</p>`;
    } catch (error) {
      els.trends.innerHTML = `<p>Trend haberler alınamadı.</p>`;
    }
  }

  async function runSearch() {
    els.status.textContent = "Aranıyor...";
    els.results.innerHTML = "";
    try {
      const payload = await searchNews(state);
      const results = Array.isArray(payload.data) ? payload.data : [];
      els.status.textContent = `${payload.total || 0} sonuç bulundu.`;
      els.results.innerHTML = results.length ? results.map(renderSearchCard).join("") : `<div class="advanced-search-empty">Aramanıza uygun haber bulunamadı.</div>`;
      els.page.textContent = String(payload.page || state.page);
      els.prev.disabled = state.page <= 1;
      els.next.disabled = !payload.hasMore;
      await loadTrends();
    } catch (error) {
      els.status.textContent = "Arama sırasında hata oluştu.";
      els.results.innerHTML = `<div class="advanced-search-empty">Arama sonuçları alınamadı.</div>`;
    }
  }

  function syncStateFromInputs(resetPage = true) {
    state.q = els.input.value.trim();
    state.category = els.category.value;
    state.source = els.source.value;
    state.dateFilter = els.date.value;
    state.startDate = els.start.value;
    state.endDate = els.end.value;
    state.sort = els.sort.value || "relevance";
    if (resetPage) state.page = 1;
  }

  async function showSuggestions() {
    const q = els.input.value.trim();
    if (q.length < 2) {
      els.suggestions.hidden = true;
      return;
    }
    const payload = await fetchSearchSuggestions(q);
    const items = Array.isArray(payload.data) ? payload.data.slice(0, 6) : [];
    if (!items.length) {
      els.suggestions.hidden = true;
      return;
    }
    els.suggestions.innerHTML = items.map((item) => `<button type="button" data-suggestion="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("");
    els.suggestions.hidden = false;
  }

  const debouncedSearch = debounce(() => { syncStateFromInputs(true); runSearch(); }, 450);
  const debouncedSuggest = debounce(showSuggestions, 300);

  els.input.addEventListener("input", () => { debouncedSuggest(); debouncedSearch(); });
  els.input.addEventListener("keydown", (event) => { if (event.key === "Enter") { syncStateFromInputs(true); runSearch(); } });
  els.submit.addEventListener("click", () => { syncStateFromInputs(true); runSearch(); });
  [els.category, els.source, els.date, els.start, els.end, els.sort].forEach((el) => el.addEventListener("change", () => { syncStateFromInputs(true); runSearch(); }));
  els.clear.addEventListener("click", () => {
    Object.assign(state, DEFAULT_STATE);
    els.input.value = ""; els.category.value = ""; els.source.value = ""; els.date.value = ""; els.start.value = ""; els.end.value = ""; els.sort.value = "relevance";
    runSearch();
  });
  els.prev.addEventListener("click", () => { if (state.page > 1) { state.page -= 1; runSearch(); } });
  els.next.addEventListener("click", () => { state.page += 1; runSearch(); });
  els.suggestions.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-suggestion]");
    if (!btn) return;
    els.input.value = btn.dataset.suggestion || "";
    els.suggestions.hidden = true;
    syncStateFromInputs(true);
    runSearch();
  });
  root.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-search-article-id]");
    if (!card) return;
    const id = card.dataset.searchArticleId;
    await trackSearchClick(id);
    toast("Arama etkileşimi kaydedildi.", "success");
  });

  loadSources().then(() => runSearch()).catch(() => runSearch());
  loadTrends();
  return { runSearch, loadTrends, state };
}
