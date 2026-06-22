"use strict";

const crypto = require("crypto");
const { URL } = require("url");

const DEFAULT_CONFIG = Object.freeze({
  duplicateThreshold: 0.85,
  discardThreshold: 0.95,
  minhashPermutations: 96,
  lshBands: 24,
  maxPairwiseFallback: 80,
  defaultSourceIcon: "/assets/sources/default-news.svg"
});

const TRACKING_KEYS = new Set([
  "fbclid", "gclid", "dclid", "igshid", "mc_cid", "mc_eid", "yclid", "msclkid",
  "spm", "utm", "ref", "ref_src", "rss", "output"
]);

function safeString(value) {
  return value == null ? "" : String(value);
}

function canonicalizeUrl(input) {
  const raw = safeString(input).trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    parsed.hash = "";
    parsed.protocol = parsed.protocol.toLowerCase();
    parsed.hostname = parsed.hostname.toLowerCase().replace(/^www\./, "");
    if (parsed.pathname !== "/") parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    const cleanParams = [];
    for (const [key, value] of parsed.searchParams.entries()) {
      const lowerKey = key.toLowerCase();
      if (lowerKey.startsWith("utm_") || TRACKING_KEYS.has(lowerKey)) continue;
      cleanParams.push([key, value]);
    }
    cleanParams.sort(([a], [b]) => a.localeCompare(b));
    parsed.search = "";
    for (const [key, value] of cleanParams) parsed.searchParams.append(key, value);
    return parsed.toString().replace(/\/$/, parsed.pathname === "/" ? "/" : "");
  } catch {
    return raw.split("#")[0];
  }
}

function sha256(value) {
  return crypto.createHash("sha256").update(safeString(value), "utf8").digest("hex");
}

function stripHtml(value) {
  return safeString(value).replace(/<[^>]*>/g, " ");
}

function normalizeText(value) {
  return stripHtml(value)
    .normalize("NFC")
    .replace(/I/g, "ı")
    .replace(/İ/g, "i")
    .toLowerCase()
    .replace(/[^0-9a-zA-ZçğıöşüÇĞİÖŞÜâîûÂÎÛ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeTitle(value) {
  let text = normalizeText(value);
  for (const prefix of ["son dakika", "breaking news", "canlı", "özel haber"]) {
    if (text.startsWith(`${prefix} `)) text = text.slice(prefix.length + 1).trim();
  }
  return text;
}

function tokenize(value) {
  return normalizeText(value).split(" ").filter((token) => token && (token.length > 1 || /^\d+$/.test(token)));
}

function shingleTokens(value, size = 3) {
  const tokens = tokenize(value);
  if (!tokens.length) return new Set();
  if (tokens.length < size) return new Set(tokens);
  const shingles = new Set();
  for (let i = 0; i <= tokens.length - size; i += 1) shingles.add(tokens.slice(i, i + size).join(" "));
  return shingles;
}

function exactArticleHash(article) {
  return sha256(`${normalizeTitle(article.title)}\n${normalizeText(article.fullText || article.content || article.description || article.summary || "")}`);
}

function contentHash(article) {
  return sha256(normalizeText(article.fullText || article.content || article.description || article.summary || ""));
}

function toArticle(raw, index) {
  const sourceUrl = canonicalizeUrl(raw.source_url || raw.sourceUrl || raw.url || raw.link || "");
  const id = safeString(raw.id || raw.article_id || raw.articleId || sourceUrl || raw.title || `article_${index}`);
  return {
    ...raw,
    id,
    title: safeString(raw.title || raw.displayTitle || raw.translatedTitle || raw.originalTitle || ""),
    summary: safeString(raw.summary || raw.description || raw.displaySummary || raw.translatedSummary || raw.originalSummary || ""),
    fullText: safeString(raw.fullText || raw.content || raw.description || raw.displayContent || raw.translatedContent || raw.originalContent || raw.summary || ""),
    sourceName: safeString(raw.source_name || raw.sourceName || raw.source || "Kaynak"),
    sourceLogo: safeString(raw.source_logo || raw.sourceLogo || raw.sourceIcon || raw.icon || ""),
    sourceUrl,
    url: sourceUrl || safeString(raw.url || raw.link || ""),
    publishedAt: safeString(raw.published_at || raw.publishedAt || raw.date || ""),
    category: safeString(raw.category || ""),
    trustScore: Number(raw.trust_score ?? raw.trustScore ?? raw.sourceTrustScore ?? 50) || 50
  };
}

class UnionFind {
  constructor(size) {
    this.parent = Array.from({ length: size }, (_, index) => index);
    this.rank = Array(size).fill(0);
  }

  find(item) {
    if (this.parent[item] !== item) this.parent[item] = this.find(this.parent[item]);
    return this.parent[item];
  }

  union(left, right) {
    let rootLeft = this.find(left);
    let rootRight = this.find(right);
    if (rootLeft === rootRight) return rootLeft;
    if (this.rank[rootLeft] < this.rank[rootRight]) {
      this.parent[rootLeft] = rootRight;
      return rootRight;
    }
    if (this.rank[rootLeft] > this.rank[rootRight]) {
      this.parent[rootRight] = rootLeft;
      return rootLeft;
    }
    this.parent[rootRight] = rootLeft;
    this.rank[rootLeft] += 1;
    return rootLeft;
  }

  groups() {
    const out = new Map();
    for (let i = 0; i < this.parent.length; i += 1) {
      const root = this.find(i);
      if (!out.has(root)) out.set(root, []);
      out.get(root).push(i);
    }
    return [...out.values()];
  }
}

function minhashSignature(text, permutations) {
  const shingles = shingleTokens(text, 3);
  const tokens = shingles.size ? [...shingles] : tokenize(text);
  const source = tokens.length ? tokens : ["__empty__"];
  const signature = [];
  for (let seed = 0; seed < permutations; seed += 1) {
    let min = Number.MAX_SAFE_INTEGER;
    for (const token of source) {
      const digest = crypto.createHash("sha1").update(`${seed}:${token}`).digest().readUInt32BE(0);
      if (digest < min) min = digest;
    }
    signature.push(min);
  }
  return signature;
}

function buildLshCandidates(articles, config) {
  const rows = config.minhashPermutations / config.lshBands;
  const buckets = new Map();
  articles.forEach((article, index) => {
    const signature = minhashSignature(`${article.title} ${article.summary} ${article.fullText}`, config.minhashPermutations);
    for (let band = 0; band < config.lshBands; band += 1) {
      const key = `${band}:${signature.slice(band * rows, band * rows + rows).join("|")}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(index);
    }
  });
  const candidates = new Set();
  for (const bucket of buckets.values()) {
    if (bucket.length < 2) continue;
    for (let i = 0; i < bucket.length; i += 1) {
      for (let j = i + 1; j < bucket.length; j += 1) {
        const left = Math.min(bucket[i], bucket[j]);
        const right = Math.max(bucket[i], bucket[j]);
        candidates.add(`${left}:${right}`);
      }
    }
  }
  return candidates;
}

function buildTfidfVectors(articles, mode = "all") {
  const docs = articles.map((article) => {
    if (mode === "title") return tokenize(normalizeTitle(article.title));
    if (mode === "content") return tokenize(article.fullText || article.summary || "");
    return tokenize(`${article.title} ${article.title} ${article.summary} ${article.fullText}`);
  });
  const df = new Map();
  for (const tokens of docs) {
    for (const token of new Set(tokens)) df.set(token, (df.get(token) || 0) + 1);
  }
  const total = Math.max(1, docs.length);
  return docs.map((tokens) => {
    const counts = new Map();
    for (const token of tokens) counts.set(token, (counts.get(token) || 0) + 1);
    const vector = new Map();
    let norm = 0;
    for (const [token, count] of counts.entries()) {
      const idf = Math.log((total + 1) / ((df.get(token) || 0) + 1)) + 1;
      const value = (1 + Math.log(count)) * idf;
      vector.set(token, value);
      norm += value * value;
    }
    norm = Math.sqrt(norm) || 1;
    for (const [token, value] of vector.entries()) vector.set(token, value / norm);
    return vector;
  });
}

function cosine(left, right) {
  if (!left.size || !right.size) return 0;
  let small = left;
  let large = right;
  if (small.size > large.size) [small, large] = [large, small];
  let score = 0;
  for (const [token, value] of small.entries()) score += value * (large.get(token) || 0);
  return score;
}

function sequenceRatio(left, right) {
  // Lightweight Dice coefficient over character bigrams; fast and deterministic.
  const a = normalizeText(left);
  const b = normalizeText(right);
  if (!a || !b) return 0;
  const bigrams = (text) => {
    const out = new Map();
    for (let i = 0; i < Math.max(1, text.length - 1); i += 1) {
      const gram = text.slice(i, i + 2);
      out.set(gram, (out.get(gram) || 0) + 1);
    }
    return out;
  };
  const leftMap = bigrams(a);
  const rightMap = bigrams(b);
  let intersection = 0;
  for (const [gram, count] of leftMap.entries()) intersection += Math.min(count, rightMap.get(gram) || 0);
  return (2 * intersection) / Math.max(1, [...leftMap.values()].reduce((s, n) => s + n, 0) + [...rightMap.values()].reduce((s, n) => s + n, 0));
}

function lexicalSimilarity(left, right) {
  const leftText = normalizeText(`${left.title} ${left.summary} ${left.fullText}`);
  const rightText = normalizeText(`${right.title} ${right.summary} ${right.fullText}`);
  const leftTokens = new Set(tokenize(leftText));
  const rightTokens = new Set(tokenize(rightText));
  if (!leftTokens.size || !rightTokens.size) return 0;
  let overlap = 0;
  for (const token of leftTokens) if (rightTokens.has(token)) overlap += 1;
  const coverage = overlap / Math.max(1, Math.min(leftTokens.size, rightTokens.size));
  const jaccard = overlap / Math.max(1, leftTokens.size + rightTokens.size - overlap);
  const sequence = sequenceRatio(leftText, rightText);
  const leftTitle = new Set(tokenize(left.title));
  const rightTitle = new Set(tokenize(right.title));
  let titleOverlap = 0;
  for (const token of leftTitle) if (rightTitle.has(token)) titleOverlap += 1;
  const titleCoverage = titleOverlap / Math.max(1, Math.min(leftTitle.size, rightTitle.size));
  if (coverage >= 0.84) return Math.min(0.97, 0.86 + (coverage - 0.84) * 0.45 + Math.max(0, sequence - 0.45) * 0.08);
  if (coverage >= 0.68 && titleCoverage >= 0.45) return Math.min(0.93, 0.85 + (coverage - 0.68) * 0.3 + Math.max(0, sequence - 0.45) * 0.08);
  return (0.52 * coverage) + (0.28 * sequence) + (0.2 * jaccard);
}

function sameTitleDifferentContentVeto(left, right, leftContentVector, rightContentVector) {
  if (normalizeTitle(left.title) !== normalizeTitle(right.title)) return false;
  if (Math.min(tokenize(left.fullText || left.summary).length, tokenize(right.fullText || right.summary).length) < 8) return false;
  return cosine(leftContentVector, rightContentVector) < 0.55;
}

function combinedSimilarity(articles, vectors, titleVectors, contentVectors, left, right) {
  const combined = cosine(vectors[left], vectors[right]);
  const title = cosine(titleVectors[left], titleVectors[right]);
  const content = cosine(contentVectors[left], contentVectors[right]);
  const weighted = (0.28 * title) + (0.72 * content);
  const lexical = lexicalSimilarity(articles[left], articles[right]);
  return Math.max(0, Math.min(1, Math.max(combined, weighted, lexical)));
}

function parseTime(value) {
  const time = Date.parse(value || "");
  return Number.isFinite(time) ? time : Number.MAX_SAFE_INTEGER;
}

function pickMainArticle(articles) {
  return [...articles].sort((a, b) => {
    const trustDiff = (Number(b.trustScore) || 50) - (Number(a.trustScore) || 50);
    if (Math.abs(trustDiff) > 0.001) return trustDiff;
    return parseTime(a.publishedAt) - parseTime(b.publishedAt);
  })[0];
}

function sourceKey(source) {
  return `${safeString(source.sourceName).toLowerCase()}|${source.sourceUrl}`;
}

function sourceEntry(article, score, status, defaultSourceIcon) {
  const sourceLogo = article.sourceLogo || article.sourceIcon || article.icon || defaultSourceIcon;
  const sourceUrl = article.sourceUrl || article.url || "";
  return {
    article_id: String(article.id),
    articleId: String(article.id),
    id: String(article.id),
    source_name: article.sourceName || article.source || "Kaynak",
    sourceName: article.sourceName || article.source || "Kaynak",
    source: article.sourceName || article.source || "Kaynak",
    source_logo: sourceLogo,
    sourceLogo,
    sourceIcon: sourceLogo,
    icon: sourceLogo,
    source_url: sourceUrl,
    sourceUrl,
    url: sourceUrl,
    title: article.title || "",
    published_at: article.publishedAt || "",
    publishedAt: article.publishedAt || "",
    summary: article.summary || article.fullText || "",
    description: article.summary || article.fullText || "",
    duplicate_score: Number(score.toFixed(4)),
    duplicateScore: Number(score.toFixed(4)),
    dedupe_status: status,
    dedupeStatus: status
  };
}

function extraInfo(main, article) {
  const mainTokens = new Set(tokenize(`${main.title} ${main.summary} ${main.fullText}`));
  const chunks = safeString(`${article.summary}. ${article.fullText}`).split(/[.!?]/).map((s) => s.trim()).filter((s) => s.length >= 40);
  for (const chunk of chunks) {
    const tokens = tokenize(chunk);
    if (!tokens.length) continue;
    const overlap = tokens.filter((token) => mainTokens.has(token)).length / tokens.length;
    if (overlap < 0.72) return chunk.slice(0, 500);
  }
  return "";
}

function clusterIdFor(main, members) {
  const seed = `${normalizeTitle(main.title)}|${main.category || ""}|${members.map((m) => m.sourceUrl || m.url || m.id).sort().join("|")}`;
  const digest = crypto.createHash("sha1").update(seed).digest("hex").slice(0, 12);
  const date = safeString(main.publishedAt || new Date().toISOString()).slice(0, 10).replace(/-/g, "_") || "unknown";
  const category = normalizeText(main.category || "gundem").replace(/\s+/g, "_") || "gundem";
  return `cluster_${date}_${category}_${digest}`;
}

function buildClusterPayload(members, pairScores, originalIndexById, config) {
  const main = pickMainArticle(members);
  let maxScore = 0;
  const rawSources = [...members].sort((a, b) => parseTime(a.publishedAt) - parseTime(b.publishedAt)).map((article) => {
    const left = originalIndexById.get(String(main.id));
    const right = originalIndexById.get(String(article.id));
    const key = left === right ? "" : `${Math.min(left, right)}:${Math.max(left, right)}`;
    const score = left === right ? 1 : (pairScores.get(key) || 0.85);
    if (left !== right) maxScore = Math.max(maxScore, score);
    const status = left === right ? "main" : (score >= config.discardThreshold ? "discarded" : "merged");
    return sourceEntry(article, score, status, config.defaultSourceIcon);
  });
  const seenSources = new Set();
  const sources = [];
  for (const source of rawSources) {
    const key = sourceKey(source);
    if (seenSources.has(key)) continue;
    seenSources.add(key);
    sources.push(source);
  }
  const duplicateStatus = sources.length <= 1
    ? "unique"
    : sources.filter((source) => source.dedupe_status !== "main").every((source) => source.dedupe_status === "discarded") ? "discarded" : "merged";
  const clusterId = clusterIdFor(main, members);
  const additionalSourceInfo = members
    .filter((article) => article.id !== main.id)
    .map((article) => ({ source_name: article.sourceName || "Kaynak", source_url: article.sourceUrl || article.url || "", detail: extraInfo(main, article) }))
    .filter((item) => item.detail);

  const payload = {
    ...main,
    id: main.id,
    title: main.title,
    summary: main.summary,
    fullText: main.fullText,
    sourceName: main.sourceName,
    sourceUrl: main.sourceUrl || main.url,
    publishedAt: main.publishedAt,
    cluster_id: clusterId,
    clusterId,
    main_article_id: main.id,
    mainArticleId: main.id,
    source_count: sources.length,
    sourceCount: sources.length,
    sources,
    duplicate_score: Number((sources.length <= 1 ? 0 : maxScore).toFixed(4)),
    duplicateScore: Number((sources.length <= 1 ? 0 : maxScore).toFixed(4)),
    dedupe_status: duplicateStatus,
    dedupeStatus: duplicateStatus,
    additional_source_info: additionalSourceInfo,
    additionalSourceInfo
  };
  payload.main_article = { ...payload };
  delete payload.main_article.main_article;
  payload.mainArticle = payload.main_article;
  payload.allTitles = [...new Set(members.map((article) => article.title).filter(Boolean))];
  payload.lastUpdatedAt = members.map((article) => article.publishedAt).filter(Boolean).sort().slice(-1)[0] || main.publishedAt || "";
  payload.relatedSources = sources.filter((source) => source.articleId !== main.id).map((source) => ({ ...source, sourceLogo: source.sourceLogo, sourceDomain: "" }));
  return payload;
}

function dedupeArticles(rawArticles, options = {}) {
  const config = { ...DEFAULT_CONFIG, ...options };
  const input = Array.isArray(rawArticles) ? rawArticles.filter(Boolean) : [];
  const articles = input.map(toArticle);
  if (articles.length <= 1) return articles.map((article, index) => buildClusterPayload([article], new Map(), new Map([[String(article.id), index]]), config));

  const uf = new UnionFind(articles.length);
  const pairScores = new Map();
  const urlSeen = new Map();
  const exactSeen = new Map();
  const contentSeen = new Map();
  const emptyContent = sha256("");

  articles.forEach((article, index) => {
    for (const [seen, key] of [[urlSeen, article.sourceUrl || article.url], [exactSeen, exactArticleHash(article)], [contentSeen, contentHash(article)]]) {
      if (!key || key === emptyContent) continue;
      if (seen.has(key)) {
        const other = seen.get(key);
        uf.union(other, index);
        pairScores.set(`${Math.min(other, index)}:${Math.max(other, index)}`, 1);
      } else {
        seen.set(key, index);
      }
    }
  });

  const candidates = buildLshCandidates(articles, config);
  if (articles.length <= config.maxPairwiseFallback) {
    for (let left = 0; left < articles.length; left += 1) {
      for (let right = left + 1; right < articles.length; right += 1) candidates.add(`${left}:${right}`);
    }
  }

  const vectors = buildTfidfVectors(articles, "all");
  const titleVectors = buildTfidfVectors(articles, "title");
  const contentVectors = buildTfidfVectors(articles, "content");
  for (const candidate of [...candidates].sort()) {
    const [left, right] = candidate.split(":").map(Number);
    if (uf.find(left) === uf.find(right)) continue;
    if (pairScores.get(candidate) >= 1) continue;
    let score = combinedSimilarity(articles, vectors, titleVectors, contentVectors, left, right);
    if (sameTitleDifferentContentVeto(articles[left], articles[right], contentVectors[left], contentVectors[right])) {
      score = Math.min(score, config.duplicateThreshold - 0.01);
    }
    if (score >= config.duplicateThreshold) {
      uf.union(left, right);
      pairScores.set(candidate, score);
    }
  }

  const indexById = new Map(articles.map((article, index) => [String(article.id), index]));
  const clusters = uf.groups().map((indexes) => buildClusterPayload(indexes.map((index) => articles[index]), pairScores, indexById, config));
  clusters.sort((a, b) => parseTime(a.publishedAt) - parseTime(b.publishedAt));
  return clusters.slice(0, Number(config.limit || clusters.length));
}

function buildDedupeStats(clusters, rawCount) {
  const totalClusters = Array.isArray(clusters) ? clusters.length : 0;
  const totalArticles = (clusters || []).reduce((sum, article) => sum + Math.max(1, Number(article.sourceCount || article.source_count || 1)), 0);
  return {
    raw: rawCount,
    clusters: totalClusters,
    grouped: Math.max(0, totalArticles - totalClusters),
    avgSourceCount: totalClusters ? Number((totalArticles / totalClusters).toFixed(2)) : 0,
    updatedAt: new Date().toISOString()
  };
}

module.exports = {
  canonicalizeUrl,
  normalizeText,
  normalizeTitle,
  dedupeArticles,
  buildDedupeStats,
  _private: {
    tokenize,
    exactArticleHash,
    contentHash,
    lexicalSimilarity,
    combinedSimilarity
  }
};
