import { trackAnalyticsEvent, getAnonymousId } from "./recommendationApi.js";

function getArticleIdFromElement(element) {
  const target = element?.closest?.("[data-article-id], [data-drag-article-id], [data-card-article-id]");
  return target?.dataset?.articleId || target?.dataset?.dragArticleId || target?.dataset?.cardArticleId || "";
}

export function initAnalyticsTracker({ showToast } = {}) {
  const sessionKey = "smartNewspaperSessionId";
  let sessionId = sessionStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = `sess_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 10)}`;
    sessionStorage.setItem(sessionKey, sessionId);
  }
  getAnonymousId();

  const send = (payload) => trackAnalyticsEvent({ session_id: sessionId, ...payload }).catch(() => {});

  document.addEventListener("click", (event) => {
    const articleId = getArticleIdFromElement(event.target);
    if (articleId) {
      send({ news_id: articleId, interaction_type: "click", metadata: { source: "article_card" } });
    }
    const categoryTarget = event.target.closest?.("[data-navbar-category], [data-category], .category-chip");
    if (categoryTarget) {
      const category = categoryTarget.dataset.navbarCategory || categoryTarget.dataset.category || categoryTarget.textContent?.trim();
      if (category) send({ interaction_type: "category_click", metadata: { category } });
    }
    const sourceTarget = event.target.closest?.("[data-source-name], [data-cluster-source]");
    if (sourceTarget) {
      const sourceName = sourceTarget.dataset.sourceName || sourceTarget.textContent?.trim();
      if (sourceName) send({ interaction_type: "source_click", metadata: { source_name: sourceName } });
    }
  }, { passive: true });

  window.smartAnalyticsTrack = send;
  return { sessionId, track: send };
}
