export function getAnonymousId() {
  const key = "smartNewspaperAnonymousId";
  let value = localStorage.getItem(key);
  if (!value) {
    value = `anon_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 10)}`;
    localStorage.setItem(key, value);
  }
  return value;
}

export async function recommendationFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Anonymous-Id": getAnonymousId(),
    ...(options.headers || {})
  };
  const token = localStorage.getItem("newspaperAuthToken");
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) throw new Error(data.message || data.error || "İstek başarısız oldu.");
  return data;
}

export function buildQuery(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value));
  });
  return qs.toString();
}

export async function loadRecommendations(params = {}) {
  const query = buildQuery(params);
  return recommendationFetch(`/api/recommendations${query ? `?${query}` : ""}`);
}

export async function loadContentRecommendations(params = {}) {
  const query = buildQuery(params);
  return recommendationFetch(`/api/recommendations/content-based${query ? `?${query}` : ""}`);
}

export async function sendRecommendationFeedback(newsId, feedback) {
  return recommendationFetch("/api/recommendations/feedback", {
    method: "POST",
    body: JSON.stringify({ news_id: newsId, feedback })
  });
}

export async function trackAnalyticsEvent(payload = {}) {
  return recommendationFetch("/api/analytics/track", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function loadAnalyticsDashboard() {
  return recommendationFetch("/api/analytics/dashboard");
}
