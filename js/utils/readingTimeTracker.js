import { trackAnalyticsEvent } from "./recommendationApi.js";

export function createReadingTimeTracker({ sessionIdProvider = () => sessionStorage.getItem("smartNewspaperSessionId") || "" } = {}) {
  let currentArticleId = "";
  let startedAt = 0;
  let activeMs = 0;
  let hiddenAt = 0;
  let heartbeat = null;

  function flush(reason = "close") {
    if (!currentArticleId || !startedAt) return;
    if (document.visibilityState !== "hidden") activeMs += Math.max(0, Date.now() - startedAt);
    const durationSeconds = Math.min(600, Math.round(activeMs / 1000));
    const articleId = currentArticleId;
    currentArticleId = "";
    startedAt = 0;
    activeMs = 0;
    clearInterval(heartbeat);
    heartbeat = null;
    if (durationSeconds >= 3) {
      trackAnalyticsEvent({
        session_id: sessionIdProvider(),
        news_id: articleId,
        interaction_type: "read",
        duration_seconds: durationSeconds,
        metadata: { reason }
      }).catch(() => {});
    }
  }

  function start(articleId) {
    if (!articleId) return;
    if (currentArticleId && currentArticleId !== String(articleId)) flush("article_change");
    currentArticleId = String(articleId);
    startedAt = Date.now();
    activeMs = 0;
    clearInterval(heartbeat);
    heartbeat = setInterval(() => {
      if (document.visibilityState === "visible" && currentArticleId) {
        const now = Date.now();
        activeMs += Math.max(0, now - startedAt);
        startedAt = now;
      }
    }, 30000);
  }

  document.addEventListener("visibilitychange", () => {
    if (!currentArticleId) return;
    if (document.visibilityState === "hidden") {
      activeMs += Math.max(0, Date.now() - startedAt);
      hiddenAt = Date.now();
    } else {
      startedAt = Date.now();
      hiddenAt = 0;
    }
  });
  window.addEventListener("beforeunload", () => flush("beforeunload"));

  return { start, flush, get currentArticleId() { return currentArticleId; } };
}
