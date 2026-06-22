export const NAVBAR_CATEGORY_MAP = Object.freeze({
  "Gündem": Object.freeze({
    type: "special",
    filter: "trending_or_latest"
  }),
  "Sağlık": Object.freeze({
    type: "label",
    value: "Sağlık"
  }),
  "Spor": Object.freeze({
    type: "label",
    value: "Spor"
  }),
  "Politika": Object.freeze({
    type: "label",
    value: "Siyaset"
  }),
  "Magazin": Object.freeze({
    type: "label",
    value: "Eğlence"
  }),
  "Teknoloji": Object.freeze({
    type: "label",
    value: "Teknoloji"
  })
});

export const NAVBAR_CATEGORY_LABELS = Object.freeze(Object.keys(NAVBAR_CATEGORY_MAP));
export const ALLOWED_NAVBAR_INTERNAL_LABELS = Object.freeze(["Teknoloji", "Siyaset", "Spor", "Ekonomi", "Eğlence", "Sağlık", "Bilim", "Dünya", "Yaşam"]);

function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function articleDateMs(article = {}) {
  const raw = article.published_at || article.publishedAt || article.date || article.time || article.createdAt || 0;
  const ms = new Date(raw).getTime();
  return Number.isFinite(ms) ? ms : 0;
}

function sourceCount(article = {}) {
  if (Number.isFinite(Number(article.source_count))) return Number(article.source_count);
  if (Number.isFinite(Number(article.sourceCount))) return Number(article.sourceCount);
  if (Array.isArray(article.sources)) return article.sources.length;
  if (Array.isArray(article.relatedSources)) return article.relatedSources.length;
  return 1;
}

function normalizeString(value) {
  return String(value || "").trim();
}

function normalizeLabels(article = {}) {
  const labels = Array.isArray(article.labels) ? article.labels : [];
  return [...new Set(labels.map(normalizeString).filter((label) => ALLOWED_NAVBAR_INTERNAL_LABELS.includes(label)))];
}

function normalizeCategory(article = {}) {
  const direct = normalizeString(article.category || article.mainCategory || article.topicCategory || article.actualCategory);
  if (direct === "Politika") return "Siyaset";
  if (direct === "Magazin") return "Eğlence";
  return direct;
}

export function buildNavbarCategorySelection(label) {
  const config = NAVBAR_CATEGORY_MAP[label];
  if (!config) return null;
  if (config.type === "special") {
    return {
      label,
      internalValue: config.filter,
      type: config.type
    };
  }
  return {
    label,
    internalValue: config.value,
    type: config.type
  };
}

export function articleMatchesNavbarCategory(article = {}, selectedCategory = null) {
  if (!selectedCategory) return true;
  if (selectedCategory.type === "special") {
    return Boolean(article.is_trending || article.isTrending)
      || toNumber(article.importance_score ?? article.importanceScore, 0) >= 0.7
      || sourceCount(article) >= 3;
  }

  const internalValue = normalizeString(selectedCategory.internalValue);
  if (!internalValue) return true;
  const labels = normalizeLabels(article);
  const category = normalizeCategory(article);

  return labels.includes(internalValue) || category === internalValue;
}

export function filterArticlesByNavbarCategory(articles = [], selectedCategory = null) {
  const list = Array.isArray(articles) ? articles.filter(Boolean) : [];
  if (!selectedCategory) return list;

  if (selectedCategory.type === "special") {
    const sortedNewest = [...list].sort((a, b) => articleDateMs(b) - articleDateMs(a));
    const matched = sortedNewest.filter((article) => articleMatchesNavbarCategory(article, selectedCategory));
    return matched.length ? matched : sortedNewest;
  }

  return list.filter((article) => articleMatchesNavbarCategory(article, selectedCategory));
}

export function navbarCategoryToSummary(selectedCategory = null) {
  if (!selectedCategory) return "";
  if (selectedCategory.type === "special") return `${selectedCategory.label}: güncel, önemli veya çok kaynaklı haberler`;
  return `${selectedCategory.label}: ${selectedCategory.internalValue} etiketiyle eşleşen haberler`;
}
