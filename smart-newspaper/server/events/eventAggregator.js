const crypto = require("crypto");
const { normalizeEvent, eventDedupeKey, normalizeText, SOURCE_META } = require("./normalizeEvent");
const { EVENT_ADAPTER_SOURCES, EVENT_FEEDS } = require("./eventSources");

const adapters = [
  require("./sources/biletixAdapter"),
  require("./sources/biletinialAdapter"),
  require("./sources/bubiletAdapter"),
  require("./sources/passoAdapter"),
  require("./sources/mobiletAdapter"),
  require("./sources/ticketmasterAdapter"),
  require("./sources/eventbriteAdapter"),
  require("./sources/meetupAdapter"),
  require("./sources/cultureIstanbulAdapter"),
  require("./sources/ibbCultureAdapter"),
  require("./sources/zorluPsmAdapter"),
  require("./sources/akmAdapter"),
  require("./sources/etkinlikIoAdapter"),
  require("./sources/festivallAdapter"),
  require("./sources/minikaAdapter"),
];

const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
let cached = null;
let cachedAt = 0;
let cachedErrors = [];

function sourceId(sourceName = "") {
  return String(sourceName).toLocaleLowerCase("tr-TR").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "source";
}

function titleTokens(title) {
  return new Set(normalizeText(title).split(" ").filter((token) => token.length > 2));
}

function jaccard(a, b) {
  const setA = titleTokens(a);
  const setB = titleTokens(b);
  if (!setA.size || !setB.size) return 0;
  let intersection = 0;
  for (const token of setA) if (setB.has(token)) intersection += 1;
  return intersection / (setA.size + setB.size - intersection);
}

function hoursApart(a, b) {
  const da = new Date(a.startDate).getTime();
  const db = new Date(b.startDate).getTime();
  if (!Number.isFinite(da) || !Number.isFinite(db)) return Infinity;
  return Math.abs(da - db) / 3_600_000;
}

function eventSimilarity(a, b) {
  const titleScore = jaccard(a.title, b.title);
  const sameCategory = a.category === b.category ? 0.15 : 0;
  const sameCity = normalizeText(a.city) === normalizeText(b.city) ? 0.10 : 0;
  const venueScore = normalizeText(a.venueName) && normalizeText(a.venueName) === normalizeText(b.venueName) ? 0.15 : 0;
  const timeScore = hoursApart(a, b) <= 48 ? 0.15 : 0;
  return titleScore * 0.45 + sameCategory + sameCity + venueScore + timeScore;
}

function clusterIdFor(event) {
  const raw = eventDedupeKey(event).split("|").slice(0, 4).join("|");
  return `evt_cluster_${crypto.createHash("sha1").update(raw).digest("hex").slice(0, 12)}`;
}

function mergeCluster(items) {
  const mainArticle = selectMainEvent(items);
  const sources = items
    .map((event) => ({
      name: event.sourceName,
      source: event.sourceName,
      sourceId: sourceId(event.sourceName),
      logo: event.sourceLogo,
      ticketUrl: event.ticketUrl,
      priceMin: event.priceMin,
      priceMax: event.priceMax,
      eventId: event.id,
      title: event.title,
      startDate: event.startDate,
      sourceEventId: event.sourceEventId
    }))
    .filter((source, index, arr) => arr.findIndex((candidate) => candidate.sourceId === source.sourceId) === index);

  return {
    ...mainArticle,
    id: mainArticle.clusterId || clusterIdFor(mainArticle),
    eventIds: items.map((event) => event.id),
    clusterId: mainArticle.clusterId || clusterIdFor(mainArticle),
    sources,
    sourceCount: sources.length,
    sourceLogo: mainArticle.sourceLogo,
    allTitles: items.map((event) => event.title),
    priceMin: minDefined(items.map((event) => event.priceMin)),
    priceMax: maxDefined(items.map((event) => event.priceMax)),
    popularityScore: Math.max(...items.map((event) => Number(event.popularityScore || 0))),
    updatedAt: new Date().toISOString()
  };
}

function minDefined(values) {
  const nums = values.filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value))).map(Number);
  return nums.length ? Math.min(...nums) : null;
}

function maxDefined(values) {
  const nums = values.filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value))).map(Number);
  return nums.length ? Math.max(...nums) : null;
}

function selectMainEvent(items) {
  return [...items].sort((a, b) => qualityScore(b) - qualityScore(a))[0];
}

function qualityScore(event) {
  const sourceTrust = SOURCE_META[event.sourceName]?.trust || 50;
  return (
    (event.imageUrl ? 20 : 0) +
    (event.description?.length > 80 ? 10 : 0) +
    (event.priceMin !== null || event.isFree ? 8 : 0) +
    sourceTrust * 0.6 +
    Number(event.popularityScore || 0) * 0.4
  );
}

function dedupeEvents(events) {
  const clusters = [];
  const rawClusters = [];

  for (const event of events) {
    let bestIndex = -1;
    let bestScore = 0;
    for (let i = 0; i < rawClusters.length; i += 1) {
      const representative = rawClusters[i][0];
      const score = eventSimilarity(event, representative);
      if (score > bestScore) {
        bestScore = score;
        bestIndex = i;
      }
    }
    if (bestScore >= 0.72 && bestIndex >= 0) {
      rawClusters[bestIndex].push(event);
    } else {
      rawClusters.push([event]);
    }
  }

  for (const group of rawClusters) {
    const cluster = mergeCluster(group);
    for (const event of group) event.clusterId = cluster.clusterId;
    clusters.push(cluster);
  }

  return clusters.sort((a, b) => new Date(a.startDate) - new Date(b.startDate));
}

function applyFilters(events, filters = {}) {
  const city = normalizeText(filters.city || "");
  const category = String(filters.category || filters.type || "Tümü");
  const source = String(filters.source || "Tüm Kaynaklar");
  const q = normalizeText(filters.q || "");
  const dateRange = resolveDateRange(filters.date || filters.dateFilter, filters.dateFrom, filters.dateTo);

  return events.filter((event) => {
    if (city && city !== "turkiye" && city !== "türkiye" && !normalizeText(event.city).includes(city)) return false;
    if (category && category !== "Tümü" && normalizeText(event.category) !== normalizeText(category)) return false;
    if (source && source !== "Tüm Kaynaklar" && source !== "Tümü") {
      const hasSource = event.sources?.some((item) => normalizeText(item.name) === normalizeText(source)) || normalizeText(event.sourceName) === normalizeText(source);
      if (!hasSource) return false;
    }
    if (q) {
      const haystack = normalizeText(`${event.title} ${event.description} ${event.venueName} ${event.city} ${event.tags?.join(" ")}`);
      if (!haystack.includes(q)) return false;
    }
    if (dateRange.from || dateRange.to) {
      const start = new Date(event.startDate).getTime();
      if (dateRange.from && start < dateRange.from.getTime()) return false;
      if (dateRange.to && start > dateRange.to.getTime()) return false;
    }
    return true;
  });
}

function resolveDateRange(label, from, to) {
  if (from || to) return { from: from ? new Date(from) : null, to: to ? new Date(to) : null };
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  const value = String(label || "");
  if (value === "Bugün") { end.setDate(start.getDate() + 1); return { from: start, to: end }; }
  if (value === "Bu Hafta") { end.setDate(start.getDate() + 7); return { from: start, to: end }; }
  if (value === "Bu Hafta Sonu") {
    const saturday = new Date(start);
    saturday.setDate(start.getDate() + ((6 - start.getDay() + 7) % 7));
    const monday = new Date(saturday);
    monday.setDate(saturday.getDate() + 2);
    return { from: saturday, to: monday };
  }
  if (value === "Bu Ay") { end.setMonth(start.getMonth() + 1); return { from: start, to: end }; }
  return { from: null, to: null };
}

async function fetchAllFromAdapters(options = {}) {
  const sourceErrors = [];
  const events = [];

  const results = await Promise.allSettled(adapters.map(async (adapter) => {
    const raw = await adapter.fetchEvents(options);
    return (Array.isArray(raw) ? raw : []).map((event) => normalizeEvent(event, adapter.source));
  }));

  results.forEach((result, index) => {
    if (result.status === "fulfilled") events.push(...result.value);
    else sourceErrors.push({ source: adapters[index]?.source?.name || `source_${index}`, message: result.reason?.message || String(result.reason) });
  });

  return { events, sourceErrors };
}

async function getAggregatedEvents(options = {}) {
  const now = Date.now();
  const force = Boolean(options.forceRefresh);
  if (!force && cached && now - cachedAt < CACHE_TTL_MS) {
    const filtered = applyFilters(cached, options);
    return paginate(filtered, options, cachedErrors);
  }

  const { events, sourceErrors } = await fetchAllFromAdapters(options);
  const clusters = dedupeEvents(events);
  cached = clusters;
  cachedAt = Date.now();
  cachedErrors = sourceErrors;
  const filtered = applyFilters(clusters, options);
  return paginate(filtered, options, sourceErrors);
}

function paginate(events, options = {}, sourceErrors = []) {
  const limit = Math.min(Math.max(Number(options.limit || 24), 1), 100);
  const page = Math.max(Number(options.page || 1), 1);
  const start = (page - 1) * limit;
  const items = events.slice(start, start + limit);
  return {
    provider: "multi-source-adapter",
    cache: { ttlMs: CACHE_TTL_MS, cachedAt: cachedAt ? new Date(cachedAt).toISOString() : null },
    filters: {
      cities: ["ISTANBUL", "ANKARA", "IZMIR", "BURSA", "ANTALYA", "ADANA", "TURKIYE"],
      types: ["Tümü", "Konser", "Tiyatro", "Festival", "Stand-up", "Spor", "Sergi", "Çocuk", "Etkinlik"],
      sources: ["Tüm Kaynaklar", ...adapters.map((item) => item.source.name)]
    },
    total: events.length,
    page,
    limit,
    hasNext: start + limit < events.length,
    events: items,
    sourceErrors: process.env.NODE_ENV === "development" ? sourceErrors : []
  };
}

function clearEventCache() {
  cached = null;
  cachedAt = 0;
  cachedErrors = [];
}

function getCachedEvents() {
  return cached || [];
}

function findEventById(id) {
  const all = cached || [];
  return all.find((event) => String(event.id) === String(id) || event.eventIds?.some((eventId) => String(eventId) === String(id))) || null;
}

function buildIcs(event) {
  const start = new Date(event.startDate);
  const end = event.endDate ? new Date(event.endDate) : new Date(start.getTime() + 2 * 60 * 60 * 1000);
  const fmt = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const esc = (v) => String(v || "").replace(/\\/g, "\\\\").replace(/,/g, "\\,").replace(/;/g, "\\;").replace(/\n/g, "\\n");
  return [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//SmartNewspaper//Events//TR",
    "BEGIN:VEVENT",
    `UID:${event.id}@smartnewspaper.local`,
    `DTSTAMP:${fmt(new Date())}`,
    `DTSTART:${fmt(start)}`,
    `DTEND:${fmt(end)}`,
    `SUMMARY:${esc(event.title)}`,
    `DESCRIPTION:${esc(event.description)}`,
    `LOCATION:${esc(event.venueName || event.city)}`,
    `URL:${esc(event.ticketUrl)}`,
    "END:VEVENT",
    "END:VCALENDAR"
  ].join("\r\n");
}

module.exports = {
  EVENT_ADAPTER_SOURCES,
  EVENT_FEEDS,
  getAggregatedEvents,
  clearEventCache,
  getCachedEvents,
  findEventById,
  dedupeEvents,
  eventSimilarity,
  buildIcs,
  sourceId
};
