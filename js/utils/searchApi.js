export function buildSearchParams(filters = {}) {
  const params = new URLSearchParams();
  const q = String(filters.q || "").trim();
  if (q) params.set("q", q.slice(0, 150));
  if (filters.category) params.set("category", filters.category);
  if (filters.source) params.set("source", filters.source);
  if (filters.dateFilter && filters.dateFilter !== "all") params.set("dateFilter", filters.dateFilter);
  if (filters.startDate) params.set("startDate", filters.startDate);
  if (filters.endDate) params.set("endDate", filters.endDate);
  if (filters.sort) params.set("sort", filters.sort);
  params.set("page", String(filters.page || 1));
  params.set("limit", String(filters.limit || 20));
  return params;
}

export async function searchNews(filters = {}) {
  const response = await fetch(`/api/search?${buildSearchParams(filters).toString()}`);
  if (!response.ok) throw new Error("Arama sonuçları alınamadı.");
  return response.json();
}

export async function fetchSearchSources() {
  const response = await fetch("/api/search/sources");
  if (!response.ok) return { success: false, data: [] };
  return response.json();
}

export async function fetchSearchSuggestions(query) {
  const q = String(query || "").trim();
  if (!q) return { success: true, data: [] };
  const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
  if (!response.ok) return { success: false, data: [] };
  return response.json();
}

export async function fetchTrends(filters = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.source) params.set("source", filters.source);
  if (filters.dateFilter) params.set("dateFilter", filters.dateFilter);
  params.set("limit", String(filters.limit || 8));
  const response = await fetch(`/api/trends?${params.toString()}`);
  if (!response.ok) throw new Error("Trend haberler alınamadı.");
  return response.json();
}

export async function trackSearchClick(articleId) {
  if (!articleId) return null;
  try {
    const response = await fetch(`/api/articles/${encodeURIComponent(articleId)}/search-click`, { method: "POST" });
    return response.ok ? response.json() : null;
  } catch {
    return null;
  }
}
