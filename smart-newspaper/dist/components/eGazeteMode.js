function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function stripHtml(value = "") {
  return String(value).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function clampText(value = "", max = 170) {
  const clean = stripHtml(value);
  if (clean.length <= max) return clean;
  return clean.slice(0, max).replace(/\s+\S*$/, "") + "...";
}

function formatDate(date = new Date()) {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    weekday: "long"
  }).format(date);
}

function issueNumber(date = new Date()) {
  const start = new Date(date.getFullYear(), 0, 0);
  const day = Math.floor((date - start) / 86400000);
  return String(date.getFullYear()).slice(2) + String(day).padStart(3, "0");
}

function safeDateLabel(article = {}) {
  const raw = article.publishedAt || article.date || article.fetchedAt || article.createdAt || "";
  if (!raw) return "Bugünün baskısı";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return String(raw);
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.max(1, Math.round(diffMs / 60000));
  if (minutes < 60) return `${minutes} dk önce`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} saat önce`;
  return new Intl.DateTimeFormat("tr-TR", { day: "2-digit", month: "short" }).format(date);
}

function categoryOf(article = {}) {
  return article.actualNewsCategory || article.category || article.primaryCategory || article.subcategory || "Gündem";
}

function sourceNameOf(article = {}) {
  return article.sourceName || article.source || article.publisher || article.author || "SmartNewspaper";
}

function articleImage(article = {}, index = 0) {
  const fromArticle = article.imageUrl || article.image || article.urlToImage || article.thumbnailUrl || article.thumbnail || article.mediaUrl || "";
  if (fromArticle) return fromArticle;
  const fallback = [
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=1200&q=80"
  ];
  return fallback[index % fallback.length];
}

function estimateReadTime(article = {}) {
  const text = stripHtml(`${article.title || ""} ${article.summary || ""} ${article.fullText || article.content || ""}`);
  const words = text ? text.split(/\s+/).length : 180;
  return article.readTime || `${Math.max(2, Math.round(words / 180))} dk`;
}

function sourceInitials(source = "") {
  const clean = String(source || "SN").replace(/https?:\/\//i, "").replace(/^www\./i, "").trim();
  const parts = clean.split(/[\s.-]+/).filter(Boolean);
  return (parts.length > 1 ? parts.slice(0, 2).map((p) => p[0]).join("") : clean.slice(0, 2)).toLocaleUpperCase("tr-TR");
}

function normalizeScore(value, fallback = 0) {
  const n = Number(value ?? fallback);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(0, Math.min(100, n));
}

function classifyArticle(article = {}) {
  if (article.egazeteLane) return article.egazeteLane;
  if (article.isExternalSource || article.sourceType || String(article.id || "").startsWith("external_")) return "Kaynaklarım";
  if (article.bookmarked || article.status === "Okundu" || normalizeScore(article.interestScore || article.relevance) >= 70) return "Sana Özel";
  if (normalizeScore(article.trendScore || article.popularity || article.importance) >= 45 || article.isTrend) return "Trend";
  return "Gündem";
}

const FALLBACK_NEWS = [
  {
    id: "egazete-fallback-1",
    title: "Merkez Bankası'ndan enflasyonla mücadelede yeni adımlar",
    summary: "Para Politikası Kurulu, sıkı para politikasının kararlılıkla sürdürüleceğini duyurdu.",
    category: "Ekonomi",
    source: "Demo Kaynak",
    interestScore: 82,
    trendScore: 77,
    imageUrl: "https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=1200&q=80"
  },
  {
    id: "egazete-fallback-2",
    title: "İstanbul'da kentsel dönüşümde yeni dönem başlıyor",
    summary: "Yeni başvuru döneminde kent genelinde güvenli yapılaşma ve dönüşüm desteği öne çıkıyor.",
    category: "Gündem",
    source: "Gündem Ajansı",
    trendScore: 69,
    imageUrl: "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1200&q=80"
  },
  {
    id: "egazete-fallback-3",
    title: "Yapay zekâ destekli asistanlar iş akışlarını değiştiriyor",
    summary: "Şirketler, günlük operasyonlarda üretken yapay zekâ araçlarını daha yoğun kullanmaya başladı.",
    category: "Bilim ve Teknoloji",
    source: "Tekno Bülten",
    interestScore: 74,
    imageUrl: "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"
  },
  {
    id: "egazete-fallback-4",
    title: "Kaynaklarından seçilen son haberler bugünkü baskıya girdi",
    summary: "Takip ettiğin RSS, haber sitesi ve YouTube kaynaklarından gelen içerikler kişisel gazetende ayrı sütunda gösteriliyor.",
    category: "Kaynaklarım",
    source: "Kaynak Merkezi",
    isExternalSource: true,
    imageUrl: "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80"
  }
];

function normalizeArticle(article = {}, index = 0) {
  const fallback = FALLBACK_NEWS[index % FALLBACK_NEWS.length];
  const raw = article && Object.keys(article).length ? article : fallback;
  const id = raw.id || raw.articleId || raw.url || raw.title || `egazete-${index}`;
  const source = sourceNameOf(raw);
  const lane = classifyArticle(raw);
  return {
    ...raw,
    id,
    articleId: id,
    clusterId: raw.clusterId || raw.cluster_id || raw.clusterKey || "",
    url: raw.url || raw.link || raw.sourceUrl || raw.originalUrl || "",
    title: raw.displayTitle || raw.title || fallback.title,
    summary: raw.summary || raw.description || raw.fullText || raw.content || fallback.summary,
    category: categoryOf(raw),
    sourceName: source,
    sourceInitials: sourceInitials(source),
    lane,
    image: articleImage(raw, index),
    readTime: estimateReadTime(raw),
    dateLabel: safeDateLabel(raw),
    pageNumber: String(index + 3).padStart(2, "0"),
    interestScore: normalizeScore(raw.interestScore || raw.relevance || raw.personalScore, lane === "Sana Özel" ? 75 : 0),
    trendScore: normalizeScore(raw.trendScore || raw.popularity || raw.importance, lane === "Trend" ? 70 : 0)
  };
}

function buildNewsData(articles = []) {
  const source = Array.isArray(articles) && articles.length ? articles : FALLBACK_NEWS;
  const seen = new Set();
  const normalized = source
    .map(normalizeArticle)
    .filter((item) => {
      const key = String(item.articleId || item.url || item.title || "");
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  if (normalized.length < 10) {
    FALLBACK_NEWS.forEach((item, index) => {
      const full = normalizeArticle(item, normalized.length + index);
      if (!seen.has(String(full.articleId || full.title))) normalized.push(full);
    });
  }
  return normalized.slice(0, 36);
}

function uniqueCategories(news = []) {
  const preferred = ["Editör", "Gündem", "Dünya", "Ekonomi", "Spor", "Bilim ve Teknoloji", "Kültür & Sanat", "Yaşam", "Kaynaklarım", "Trend"];
  const dataCategories = [...new Set(news.map((item) => item.category).filter(Boolean))].slice(0, 4);
  return [...new Set([...preferred, ...dataCategories])].slice(0, 10);
}

function scoreForHeadline(item = {}) {
  const personal = normalizeScore(item.interestScore);
  const trend = normalizeScore(item.trendScore);
  const sourceBoost = item.lane === "Kaynaklarım" ? 8 : 0;
  const bookmarkBoost = item.bookmarked ? 15 : 0;
  return personal * 0.55 + trend * 0.35 + sourceBoost + bookmarkBoost;
}

function filterByActiveCategory(news = [], activeCategory = "Editör") {
  if (!activeCategory || activeCategory === "Editör") return news;
  if (activeCategory === "Trend") return news.filter((item) => item.lane === "Trend" || item.trendScore >= 45);
  if (activeCategory === "Kaynaklarım") return news.filter((item) => item.lane === "Kaynaklarım" || item.isExternalSource);
  const key = activeCategory.toLocaleLowerCase("tr-TR");
  return news.filter((item) => `${item.category} ${item.lane}`.toLocaleLowerCase("tr-TR").includes(key));
}

function pageSlice(news = [], start = 0, count = 8) {
  const safe = news.length ? news : buildNewsData([]);
  const out = [];
  for (let i = 0; i < count; i += 1) out.push(safe[(start + i) % safe.length]);
  return out;
}

function getWeatherLabel() {
  try {
    const raw = localStorage.getItem("smart_newspaper_weather");
    if (!raw) return { text: "İstanbul", temp: "22°C", icon: "fa-sun" };
    const weather = JSON.parse(raw);
    return {
      text: weather.city || weather.name || "İstanbul",
      temp: weather.temp != null ? `${weather.temp}°C` : "22°C",
      icon: weather.main === "Rain" ? "fa-cloud-rain" : weather.main === "Clouds" ? "fa-cloud-sun" : "fa-sun"
    };
  } catch {
    return { text: "İstanbul", temp: "22°C", icon: "fa-sun" };
  }
}

function safePercent(value, prefix = "+") {
  const n = Number(value);
  const formatted = Number.isFinite(n) ? n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0,68";
  return `${prefix}${formatted}%`;
}

export class EGazeteMode {
  constructor(options = {}) {
    this.getArticles = options.getArticles || (() => []);
    this.getProfile = options.getProfile || (() => ({}));
    this.onArticleAction = options.onArticleAction || (() => {});
    this.container = null;
    this.news = [];
    this.activeCategory = "Editör";
    this.currentSpread = 0;
    this._delegatedContainer = null;
    this._articleClickHandler = null;
    this._articleKeyHandler = null;
    this._transitionTimer = null;
    try {
      this.isSourcePanelCollapsed = localStorage.getItem("smart_newspaper_eg_source_panel_collapsed_v3") === "1";
    } catch {
      this.isSourcePanelCollapsed = false;
    }
  }

  open() {
    if (typeof window.showPage === "function") window.showPage("egazete");
    const target = document.getElementById("egazete-dashboard-section") || this.container;
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  close() {
    if (typeof window.showPage === "function") window.showPage("feed");
  }

  renderDashboard(container) {
    if (!container) return;
    this.container = container;
    const sourceArticles = Array.isArray(this.getArticles()) ? this.getArticles() : [];
    this.news = buildNewsData(sourceArticles);
    const categories = uniqueCategories(this.news);
    if (!categories.includes(this.activeCategory)) this.activeCategory = "Editör";
    const filtered = filterByActiveCategory(this.news, this.activeCategory);
    const paper = filtered.length ? filtered : this.news;
    const spreadCount = Math.max(1, Math.ceil(paper.length / 4));
    this.currentSpread = Math.max(0, Math.min(this.currentSpread, spreadCount - 1));
    const weather = getWeatherLabel();
    const profile = this.getProfile() || {};
    const start = this.currentSpread * 4;
    const spreadArticles = pageSlice(paper, start, 4);
    const headline = [...spreadArticles].sort((a, b) => scoreForHeadline(b) - scoreForHeadline(a))[0] || spreadArticles[0];
    const secondLeft = spreadArticles.find((item) => item.articleId !== headline.articleId) || pageSlice(paper, start + 1, 1)[0];
    const rightPageArticles = pageSlice(paper, start + 2, 2);
    const sources = this.pickLane("Kaynaklarım", 8, this.news, start + 4);

    container.innerHTML = `
      <div class="eg eg-v2 ${this.isSourcePanelCollapsed ? "is-source-collapsed" : ""}" aria-label="Kişisel e-Gazete Okuma Modu">
        ${this.renderTopBar(weather, profile)}
        ${this.renderTabs(categories)}
        <main class="eg-reader-shell ${this.currentSpread > 0 ? "is-later-spread" : ""}" data-eg-spread>
          <div class="eg-paper-stack" aria-hidden="true"><span></span><span></span><span></span></div>
          <div class="eg-reader-layout eg-reference-layout" data-eg-reader-layout>
            <div style="display: flex; flex-direction: column; min-width: 0;">
              <section class="eg-newspaper-spread" aria-label="Gazete sayfaları">
                ${this.renderFrontPage(headline, secondLeft, profile)}
                ${this.renderCenterPage(rightPageArticles)}
              </section>
              ${this.renderReaderControls(spreadCount)}
            </div>
            ${this.renderSourceDrawer(sources, paper)}
          </div>
        </main>
      </div>
    `;

    this.bindArticleDelegation(container);
    this.bindControls(container, categories, spreadCount);
  }

  pickLane(lane, count, articles = this.news, offset = 0) {
    const filtered = articles.filter((item) => item.lane === lane || (lane === "Trend" && item.trendScore >= 45));
    return pageSlice(filtered.length ? filtered : articles, offset, count);
  }

  articleAttrs(item) {
    const id = escapeHtml(String(item?.articleId || item?.id || ""));
    const clusterId = item?.clusterId ? ` data-cluster-id="${escapeHtml(String(item.clusterId))}"` : "";
    const url = item?.url ? ` data-url="${escapeHtml(String(item.url))}"` : "";
    const title = escapeHtml(stripHtml(item?.title || "Haber"));
    return `data-eg-article-card data-eid="${id}" data-article-id="${id}"${clusterId}${url} role="button" tabindex="0" aria-label="Haberi aç: ${title}"`;
  }

  renderTopBar(weather, profile) {
    const name = profile?.name || "Okuyucu";
    const initials = String(name).split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toLocaleUpperCase("tr-TR") || "SN";
    return `
      <header class="eg-topbar">
        <div class="eg-top-left">
          <button type="button" class="eg-menu" data-eg-interactive aria-label="Menü"><i class="fa-solid fa-bars"></i></button>
          <div>
            <h1>e-Gazete Modu <i class="fa-solid fa-chevron-down"></i></h1>
            <p>${escapeHtml(name)} için kişiselleştirilmiş günlük baskı</p>
          </div>
        </div>
        <div class="eg-top-metrics">
          <div class="eg-top-metric eg-date"><i class="fa-regular fa-calendar-days"></i><strong>${escapeHtml(formatDate())}</strong><span>Sayı: ${issueNumber()}</span></div>
          <div class="eg-top-metric eg-weather"><i class="fa-regular ${weather.icon}"></i><strong>${escapeHtml(weather.text)}</strong><span>${escapeHtml(weather.temp)}</span></div>
          <div class="eg-top-metric"><strong>BIST 100</strong><span>9.856,10 <b class="pos">${safePercent(0.68)}</b></span></div>
          <div class="eg-top-metric"><strong>USD/TRY</strong><span>32,18 <b class="neg">-0,15%</b></span></div>
          <div class="eg-top-metric"><strong>EUR/TRY</strong><span>34,72 <b class="pos">+0,22%</b></span></div>
        </div>
        <div class="eg-top-actions">
          <button type="button" data-eg-interactive class="eg-search"><i class="fa-solid fa-magnifying-glass"></i><span>Ara</span></button>
          <button type="button" data-eg-interactive class="eg-search"><i class="fa-regular fa-bookmark"></i><span>Kaydedilenler</span></button>
          <button type="button" data-eg-interactive id="eg-pdf-btn" class="eg-pdf"><i class="fa-regular fa-file-pdf"></i> PDF İndir</button>
          <span class="eg-avatar">${escapeHtml(initials)}</span>
        </div>
      </header>
    `;
  }

  renderTabs(categories) {
    return `
      <nav class="eg-news-tabs" aria-label="E-Gazete kategorileri">
        ${categories.map((category) => `
          <button type="button" data-eg-interactive data-eg-category="${escapeHtml(category)}" class="${category === this.activeCategory ? "is-active" : ""}">${escapeHtml(category)}</button>
        `).join("")}
      </nav>
    `;
  }

  renderFrontPage(headline, secondary, profile) {
    const second = secondary && secondary.articleId !== headline.articleId ? secondary : pageSlice(this.news, 1, 1)[0] || headline;
    return `
      <article class="eg-sheet eg-front-page eg-two-news-page" aria-label="Birinci gazete sayfası">
        <div class="eg-paper-head">
          <small>GÜNLÜK KİŞİSEL GAZETE</small>
          <h2>${escapeHtml(profile?.paperName || "Smart Newspaper")}</h2>
          <div><span>${escapeHtml(formatDate())}</span><span>Sayı: ${issueNumber()}</span><span>smartnewspaper.local</span></div>
        </div>
        <section class="eg-page-story eg-page-story-main" ${this.articleAttrs(headline)}>
          <div class="eg-overline">MANŞET · ${escapeHtml(headline.lane || headline.category)}</div>
          <h3>${escapeHtml(headline.title)}</h3>
          <p>${escapeHtml(clampText(headline.summary, 175))}</p>
          <small>Sayfa ${escapeHtml(headline.pageNumber)} · ${escapeHtml(headline.sourceName)} · ${escapeHtml(headline.dateLabel)}</small>
          <img src="${escapeHtml(headline.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        </section>
        <section class="eg-page-story eg-page-story-secondary" ${this.articleAttrs(second)}>
          <div>
            <span>${escapeHtml(second.category || "Gündem")}</span>
            <h4>${escapeHtml(second.title)}</h4>
            <p>${escapeHtml(clampText(second.summary, 130))}</p>
            <small>${escapeHtml(second.sourceName)} · Sayfa ${escapeHtml(second.pageNumber)} · ${escapeHtml(second.dateLabel)}</small>
          </div>
          <img src="${escapeHtml(second.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        </section>
      </article>
    `;
  }

  renderCenterPage(articles = []) {
    const main = articles[0] || this.news[0];
    const second = articles[1] || this.news[1] || main;
    return `
      <article class="eg-sheet eg-center-page eg-two-news-page" aria-label="İkinci gazete sayfası">
        <div class="eg-sheet-meta"><span>${escapeHtml(String((this.currentSpread * 2) + 2).padStart(2, "0"))}</span><b>GÜNDEM & TREND</b><small>AKTÜEL GAZETE</small></div>
        <section class="eg-page-story eg-page-story-main eg-page-story-horizontal" ${this.articleAttrs(main)}>
          <div>
            <h3>${escapeHtml(main.title)}</h3>
            <p>${escapeHtml(clampText(main.summary, 155))}</p>
            <small>Sayfa ${escapeHtml(main.pageNumber)} · ${escapeHtml(main.sourceName)} · ${escapeHtml(main.dateLabel)}</small>
          </div>
          <img src="${escapeHtml(main.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        </section>
        <section class="eg-page-story eg-page-story-secondary eg-page-story-horizontal" ${this.articleAttrs(second)}>
          <div>
            <span>${escapeHtml(second.category || "Gündem")}</span>
            <h4>${escapeHtml(second.title)}</h4>
            <p>${escapeHtml(clampText(second.summary, 145))}</p>
            <small>${escapeHtml(second.sourceName)} · Sayfa ${escapeHtml(second.pageNumber)} · ${escapeHtml(second.dateLabel)}</small>
          </div>
          <img src="${escapeHtml(second.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        </section>
      </article>
    `;
  }

  renderSourceDrawer(sources, paper) {
    const label = this.isSourcePanelCollapsed ? "Kaynak panelini aç" : "Kaynak panelini gizle";
    return `
      <aside class="eg-source-drawer ${this.isSourcePanelCollapsed ? "is-collapsed" : "is-open"}" data-eg-source-drawer aria-label="Seçtiğiniz kaynaklar paneli">
        <button type="button" class="eg-source-toggle" data-eg-interactive data-eg-source-toggle aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">
          <i class="fa-solid ${this.isSourcePanelCollapsed ? "fa-chevron-left" : "fa-chevron-right"}"></i>
          <span>${this.isSourcePanelCollapsed ? "Kaynaklar" : "Gizle"}</span>
        </button>
        <button type="button" class="eg-source-floating-tab" data-eg-interactive data-eg-source-open aria-label="Kaynak panelini aç">
          <i class="fa-solid fa-newspaper"></i>
          <span>Kaynaklar</span>
        </button>
        <div class="eg-source-drawer-body">
          ${this.renderSourcePage(sources, paper)}
        </div>
      </aside>
    `;
  }

  renderSourcePage(sources, paper) {
    const sourceItems = (sources.length ? sources : paper).slice(0, 5);
    const authors = paper.filter((item) => !sourceItems.some((s) => s.articleId === item.articleId)).slice(0, 2);
    return `
      <aside class="eg-sheet eg-source-page">
        <div class="eg-source-head"><h3>SEÇTİĞİNİZ KAYNAKLAR</h3><button type="button" data-eg-interactive>Daha fazla <i class="fa-solid fa-angle-right"></i></button></div>
        <div class="eg-source-list">
          ${sourceItems.map((item) => `
            <article class="eg-source-item" ${this.articleAttrs(item)}>
              <div class="eg-source-logo">${escapeHtml(item.sourceInitials)}</div>
              <div class="eg-source-copy">
                <strong>${escapeHtml(clampText(item.title, 76))}</strong>
                <span>Kaynak: ${escapeHtml(item.sourceName)} · ${escapeHtml(item.dateLabel)}</span>
              </div>
              <img src="${escapeHtml(item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
            </article>
          `).join("")}
        </div>
        <div class="eg-source-head eg-writer-head"><h3>KÖŞE / ANALİZ</h3><button type="button" data-eg-interactive>Tümü <i class="fa-solid fa-angle-right"></i></button></div>
        <div class="eg-writer-list">
          ${authors.map((item, index) => `
            <article class="eg-writer-item" ${this.articleAttrs(item)}>
              <div class="eg-writer-avatar">${escapeHtml(sourceInitials(item.sourceName || `Y${index + 1}`))}</div>
              <div><b>${escapeHtml(item.sourceName)}</b><p>${escapeHtml(clampText(item.title, 78))}</p><small>Sayfa ${escapeHtml(item.pageNumber)}</small></div>
            </article>
          `).join("")}
        </div>
      </aside>
    `;
  }

  renderMiniStory(item, className = "") {
    return `
      <article class="eg-mini-story ${className}" ${this.articleAttrs(item)}>
        <span>${escapeHtml(item.category)}</span>
        <h4>${escapeHtml(clampText(item.title, 62))}</h4>
        <small>${escapeHtml(item.sourceName)} · Sayfa ${escapeHtml(item.pageNumber)}</small>
        <img src="${escapeHtml(item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
      </article>
    `;
  }

  renderColumnStory(item) {
    return `
      <article class="eg-column-story" ${this.articleAttrs(item)}>
        <h4>${escapeHtml(clampText(item.title, 72))}</h4>
        <p>${escapeHtml(clampText(item.summary, 90))}</p>
        <img src="${escapeHtml(item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">
        <small>${escapeHtml(item.sourceName)} · Sayfa ${escapeHtml(item.pageNumber)}</small>
      </article>
    `;
  }

  renderReaderControls(spreadCount) {
    return `
      <footer class="eg-reader-controls" data-eg-interactive>
        <button type="button" class="eg-control-btn" data-eg-toc><i class="fa-solid fa-list"></i> İçindekiler</button>
        <div class="eg-page-nav">
          <button type="button" data-eg-prev ${this.currentSpread === 0 ? "disabled" : ""} aria-label="Önceki sayfa"><i class="fa-solid fa-chevron-left"></i></button>
          <strong>${this.currentSpread * 2 + 1}-${Math.min(this.currentSpread * 2 + 3, spreadCount * 2 + 1)} / ${Math.max(3, spreadCount * 2 + 1)}</strong>
          <button type="button" data-eg-next ${this.currentSpread >= spreadCount - 1 ? "disabled" : ""} aria-label="Sonraki sayfa"><i class="fa-solid fa-chevron-right"></i></button>
        </div>
        <div class="eg-view-tools">
          <button type="button"><i class="fa-solid fa-table-cells-large"></i> Görünüm</button>
          <button type="button"><i class="fa-solid fa-minus"></i> Yakınlaştır <b>%100</b> <i class="fa-solid fa-plus"></i></button>
          <button type="button"><i class="fa-solid fa-volume-high"></i> Sesli Oku</button>
        </div>
      </footer>
    `;
  }

  bindControls(container, categories, spreadCount) {
    container.querySelector("#eg-pdf-btn")?.addEventListener("click", () => this.printPdf());
    container.querySelector("[data-eg-prev]")?.addEventListener("click", () => this.turnPage(-1, spreadCount));
    container.querySelector("[data-eg-next]")?.addEventListener("click", () => this.turnPage(1, spreadCount));
    container.querySelectorAll("[data-eg-category]").forEach((button) => {
      button.addEventListener("click", () => {
        this.activeCategory = button.dataset.egCategory || "Editör";
        this.currentSpread = 0;
        this.renderDashboard(container);
      });
    });
    container.querySelector("[data-eg-source-toggle]")?.addEventListener("click", () => this.toggleSourcePanel(container));
    container.querySelector("[data-eg-source-open]")?.addEventListener("click", () => this.toggleSourcePanel(container, false));
    container.querySelector("[data-eg-toc]")?.addEventListener("click", () => {
      if (typeof window.showToast === "function") {
        window.showToast("İçindekiler: Sana Özel, Gündem, Trend ve Kaynaklarım sayfaları birlikte hazırlandı.", "info");
      }
    });
  }

  toggleSourcePanel(container, forceCollapsed = null) {
    this.isSourcePanelCollapsed = typeof forceCollapsed === "boolean" ? forceCollapsed : !this.isSourcePanelCollapsed;
    try {
      localStorage.setItem("smart_newspaper_eg_source_panel_collapsed_v3", this.isSourcePanelCollapsed ? "1" : "0");
    } catch {}
    this.renderDashboard(container || this.container);
  }

  turnPage(direction, spreadCount) {
    const next = Math.max(0, Math.min(spreadCount - 1, this.currentSpread + direction));
    if (next === this.currentSpread || !this.container) return;
    const shell = this.container.querySelector("[data-eg-spread]");
    shell?.classList.add(direction > 0 ? "is-turning-next" : "is-turning-prev");
    clearTimeout(this._transitionTimer);
    this._transitionTimer = setTimeout(() => {
      this.currentSpread = next;
      this.renderDashboard(this.container);
    }, 210);
  }

  bindArticleDelegation(container) {
    if (!container) return;
    if (this._delegatedContainer && this._delegatedContainer !== container) {
      this._delegatedContainer.removeEventListener("click", this._articleClickHandler);
      this._delegatedContainer.removeEventListener("keydown", this._articleKeyHandler);
      this._delegatedContainer = null;
    }
    if (this._delegatedContainer === container) return;
    this._articleClickHandler = (event) => {
      const card = this.getArticleCardFromEvent(event);
      if (!card) return;
      event.preventDefault();
      this.openEGazeteArticle(card.dataset.articleId || card.dataset.eid);
    };
    this._articleKeyHandler = (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const card = this.getArticleCardFromEvent(event);
      if (!card) return;
      event.preventDefault();
      this.openEGazeteArticle(card.dataset.articleId || card.dataset.eid);
    };
    container.addEventListener("click", this._articleClickHandler);
    container.addEventListener("keydown", this._articleKeyHandler);
    this._delegatedContainer = container;
  }

  getArticleCardFromEvent(event) {
    const target = event.target;
    if (!(target instanceof Element)) return null;
    if (target.closest("button, a, input, select, textarea, [data-eg-interactive]")) return null;
    const card = target.closest("[data-eg-article-card]");
    if (!card || !this.container?.contains(card)) return null;
    return card;
  }

  handleArticleOpen(id) {
    const articleId = String(id || "").trim();
    if (!articleId) return;
    const article = Array.isArray(this.getArticles())
      ? this.getArticles().find((item) => String(item.id || item.articleId) === articleId)
      : null;
    if (article) {
      this.onArticleAction("detail", article.id || article.articleId);
      return;
    }
    const normalized = this.news.find((item) => String(item.articleId || item.id) === articleId);
    if (normalized?.url) {
      window.open(normalized.url, "_blank", "noopener,noreferrer");
      return;
    }
    if (typeof window.showToast === "function") {
      window.showToast("Bu haberin detay kaydı bulunamadı; kaynak bağlantısı yoksa sadece gazete önizlemesinde gösterilir.", "info");
    }
  }

  openEGazeteArticle(id) {
    this.handleArticleOpen(id);
  }

  printPdf() {
    const params = new URLSearchParams({
      mode: "inline",
      personalized: "true",
      includeUserSources: "true",
      includeTrending: "true",
      layout: "egazete",
      language: "tr"
    });
    if (typeof window.showToast === "function") {
      window.showToast("PDF hazırlanıyor; kişisel, trend ve kaynak haberleri birlikte basılıyor...", "info");
    }
    window.open(`/api/export/pdf?${params.toString()}`, "_blank", "noopener,noreferrer");
  }
}
