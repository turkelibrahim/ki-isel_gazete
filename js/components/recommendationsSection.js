import { loadRecommendations, sendRecommendationFeedback, trackAnalyticsEvent } from "../utils/recommendationApi.js";

function escapeHtml(value = "") {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
}

function safeId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `rec_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 10)}`;
}

function articleImage(article = {}) {
  return article.image_url || article.imageUrl || article.urlToImage || article.image || "/assets/news-placeholder.jpg";
}

function articleSource(article = {}) {
  return article.source_name || article.sourceName || article.source || "Kaynak belirtilmedi";
}

function articleSources(article = {}) {
  if (Array.isArray(article.sources) && article.sources.length) return article.sources;
  return [{ name: articleSource(article), source_name: articleSource(article), icon: article.sourceIcon || article.icon || "" }];
}

function normalizeRecommendation(article = {}) {
  const id = article.id || article.news_id || article.newsId || safeId();
  const sources = articleSources(article);
  return {
    ...article,
    id,
    news_id: article.news_id || id,
    cluster_id: article.cluster_id || article.clusterId || id,
    title: article.title || article.displayTitle || article.originalTitle || "Başlık bulunamadı",
    summary: article.summary || article.description || article.displaySummary || article.originalSummary || article.content?.slice?.(0, 180) || "Bu haber için özet bulunamadı.",
    category: article.category || "Genel",
    labels: Array.isArray(article.labels) ? article.labels : [],
    source_name: articleSource(article),
    sources,
    source_count: Number(article.source_count || article.sourceCount || sources.length || 1),
    published_at: article.published_at || article.publishedAt || article.created_at || article.date || null,
    image_url: articleImage(article),
    url: article.url || article.sourceUrl || article.link || "#",
    recommendation_score: Number(article.recommendation_score || 0),
    content_similarity_score: Number(article.content_similarity_score || 0),
    reason: article.reason || "İlgi alanlarınıza uygun olabileceği için önerildi."
  };
}

function renderSourceIcons(article = {}) {
  const sources = articleSources(article).slice(0, 8);
  if (!sources.length) return "";
  return `<div class="recommendation-source-icons" aria-label="Bu haberi yazan kaynaklar">
    ${sources.map((source) => {
      const name = source.name || source.source_name || source.sourceName || source.title || articleSource(article);
      const icon = source.icon || source.logo || source.favicon || source.image || "";
      return `<span class="recommendation-source-icon" title="${escapeHtml(name)}">${icon ? `<img src="${escapeHtml(icon)}" alt="" loading="lazy" />` : escapeHtml(String(name).slice(0, 2).toUpperCase())}</span>`;
    }).join("")}
    ${Number(article.source_count || 0) > sources.length ? `<span class="recommendation-source-more">+${Number(article.source_count) - sources.length}</span>` : ""}
  </div>`;
}

function renderCard(rawArticle = {}) {
  const article = normalizeRecommendation(rawArticle);
  const id = article.news_id || article.id;
  const image = article.image_url;
  return `
    <article class="recommendation-card" data-recommendation-id="${escapeHtml(id)}" data-article-id="${escapeHtml(id)}">
      <div class="recommendation-image ${image ? "" : "is-placeholder"}">${image ? `<img src="${escapeHtml(image)}" alt="" loading="lazy" />` : `<i class="fa-regular fa-newspaper"></i>`}</div>
      <div class="recommendation-body">
        <div class="recommendation-meta"><span>${escapeHtml(article.category)}</span><span>${escapeHtml(article.source_name)}</span></div>
        <h4>${escapeHtml(article.title)}</h4>
        <p>${escapeHtml(article.summary)}</p>
        ${renderSourceIcons(article)}
        <em class="recommendation-reason"><i class="fa-solid fa-wand-magic-sparkles"></i> ${escapeHtml(article.reason)}</em>
        <div class="recommendation-score-row">
          <span>Skor: ${Number(article.recommendation_score || 0).toFixed(1)}</span>
          <span>Benzerlik: ${Number(article.content_similarity_score || 0).toFixed(1)}</span>
        </div>
        <div class="recommendation-actions">
          <button type="button" data-rec-feedback="interested" data-news-id="${escapeHtml(id)}">İlgimi çekti</button>
          <button type="button" data-rec-feedback="not_interested" data-news-id="${escapeHtml(id)}">İlgimi çekmedi</button>
          <button type="button" data-rec-feedback="show_less" data-news-id="${escapeHtml(id)}">Daha az göster</button>
        </div>
      </div>
    </article>`;
}

export function initRecommendationsSection({ showToast, fallbackArticlesProvider } = {}) {
  const roots = Array.from(document.querySelectorAll("[data-recommendations-root], #recommendations-root"));
  if (!roots.length) return null;
  let observer = null;
  let lastItems = [];

  function setAll(html) {
    roots.forEach((root) => { root.innerHTML = html; });
  }

  function bindRenderedItems(items = []) {
    roots.forEach((root) => {
      root.querySelector("#recommendation-refresh")?.addEventListener("click", load);
      root.querySelectorAll("[data-rec-feedback]").forEach((button) => {
        button.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          try {
            await sendRecommendationFeedback(button.dataset.newsId, button.dataset.recFeedback);
            button.closest(".recommendation-card")?.classList.add("feedback-sent");
            showToast?.("Öneri geri bildirimi kaydedildi.");
          } catch (error) {
            showToast?.(error.message || "Geri bildirim kaydedilemedi.");
          }
        });
      });
      root.querySelectorAll(".recommendation-card").forEach((card) => {
        card.addEventListener("click", () => {
          const articleId = card.dataset.articleId;
          const article = items.find((item) => String(item.news_id || item.id) === String(articleId));
          trackAnalyticsEvent({
            news_id: articleId,
            interaction_type: "recommendation_click",
            metadata: { source: "recommendations", recommendation_score: article?.recommendation_score || 0 }
          }).catch(() => {});
          if (window.showDetail) window.showDetail(articleId);
        });
      });
    });

    observer?.disconnect?.();
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.dataset.recommendationId;
            const article = items.find((item) => String(item.news_id || item.id) === String(id));
            trackAnalyticsEvent({
              news_id: id,
              interaction_type: "recommendation_impression",
              metadata: { source: "recommendations", recommendation_score: article?.recommendation_score || 0 }
            }).catch(() => {});
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.55 });
      roots.forEach((root) => root.querySelectorAll(".recommendation-card").forEach((card) => observer.observe(card)));
    }
  }

  function localFallbackItems() {
    const local = typeof fallbackArticlesProvider === "function" ? fallbackArticlesProvider() : [];
    return (Array.isArray(local) ? local : []).slice(0, 12).map((article, index) => normalizeRecommendation({
      ...article,
      recommendation_score: article.recommendation_score || Math.max(30, 75 - index * 3),
      content_similarity_score: article.content_similarity_score || 0,
      reason: article.reason || "Güncel haber akışından güvenli fallback olarak önerildi."
    }));
  }

  async function load() {
    setAll(`<div class="recommendation-state"><i class="fa-solid fa-spinner fa-spin"></i><span>Sizin için öneriler hazırlanıyor...</span></div>`);
    try {
      const data = await loadRecommendations({ limit: 12, excludeRead: true });
      let items = Array.isArray(data.data) ? data.data.map(normalizeRecommendation) : [];
      if (!items.length) items = localFallbackItems();
      lastItems = items;
      if (!items.length) {
        setAll(`<div class="recommendation-state"><i class="fa-regular fa-compass"></i><strong>Henüz size özel öneri oluşturacak yeterli veri yok.</strong><p>Popüler ve güncel haberleri okumaya başladıkça önerileriniz burada görünecek.</p></div>`);
        return;
      }
      setAll(`
        <div class="recommendation-header">
          <div><p class="kicker"><i class="fa-solid fa-sparkles"></i> Kişisel öneri motoru</p><h2>Sizin İçin Önerilenler</h2></div>
          <button type="button" class="recommendation-refresh" id="recommendation-refresh"><i class="fa-solid fa-rotate"></i> Yenile</button>
        </div>
        <div class="recommendation-grid">${items.map(renderCard).join("")}</div>`);
      bindRenderedItems(items);
    } catch (error) {
      const fallback = localFallbackItems();
      if (fallback.length) {
        lastItems = fallback;
        setAll(`
          <div class="recommendation-header">
            <div><p class="kicker"><i class="fa-solid fa-triangle-exclamation"></i> Güvenli öneri modu</p><h2>Sizin İçin Önerilenler</h2><p class="recommendation-safe-note">Öneriler yüklenirken bir sorun oluştu; güncel haberlerden öneriler gösteriliyor.</p></div>
            <button type="button" class="recommendation-refresh" id="recommendation-refresh"><i class="fa-solid fa-rotate"></i> Yenile</button>
          </div>
          <div class="recommendation-grid">${fallback.map(renderCard).join("")}</div>`);
        bindRenderedItems(fallback);
        return;
      }
      setAll(`<div class="recommendation-state error"><i class="fa-solid fa-triangle-exclamation"></i><strong>Öneriler yüklenirken bir sorun oluştu.</strong><p>${escapeHtml(error.message || "Güncel haberlerden öneriler gösterilemiyor.")}</p></div>`);
    }
  }

  return { load, get items() { return lastItems; } };
}
