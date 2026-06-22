const crypto = require("crypto");

const CATEGORY_ALIASES = [
  [/konser|müzik|music|jazz|rock|dj|akustik/i, "Konser"],
  [/tiyatro|sahne|müzikal|opera|bale|oyun/i, "Tiyatro"],
  [/festival|fest|şenlik|kültür yolu/i, "Festival"],
  [/stand\s*-?up|komedi|gösteri/i, "Stand-up"],
  [/spor|maç|futbol|basket|voleybol|stadyum/i, "Spor"],
  [/sergi|müze|galeri|bienal|dijital sanat/i, "Sergi"],
  [/atölye|workshop|eğitim|seminer/i, "Atölye"],
  [/fuar|expo/i, "Fuar"],
  [/söyleşi|panel|konferans/i, "Söyleşi"],
  [/kültür|sanat|opera|bale|klasik müzik/i, "Kültür Sanat"],
  [/çocuk|aile|kids/i, "Çocuk"],
];

const FALLBACK_IMAGES = {
  "Konser": "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?auto=format&fit=crop&w=1000&q=80",
  "Tiyatro": "https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&fit=crop&w=1000&q=80",
  "Festival": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?auto=format&fit=crop&w=1000&q=80",
  "Stand-up": "https://images.unsplash.com/photo-1527224857830-43a7acc85260?auto=format&fit=crop&w=1000&q=80",
  "Spor": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=1000&q=80",
  "Sergi": "https://images.unsplash.com/photo-1518998053901-5348d3961a04?auto=format&fit=crop&w=1000&q=80",
  "Çocuk": "https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9?auto=format&fit=crop&w=1000&q=80",
  "Atölye": "https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1000&q=80",
  "Fuar": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=1000&q=80",
  "Söyleşi": "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?auto=format&fit=crop&w=1000&q=80",
  "Kültür Sanat": "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?auto=format&fit=crop&w=1000&q=80",
  "Etkinlik": "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1000&q=80"
};

const SOURCE_META = {
  "Biletix": { logo: "/assets/events/sources/biletix.svg", trust: 90 },
  "Bubilet": { logo: "/assets/events/sources/bubilet.svg", trust: 86 },
  "Passo": { logo: "/assets/events/sources/passo.svg", trust: 88 },
  "Mobilet": { logo: "/assets/events/sources/mobilet.svg", trust: 84 },
  "Biletinial": { logo: "/assets/events/sources/biletinial.svg", trust: 84 },
  "Ticketmaster": { logo: "/assets/events/sources/ticketmaster.svg", trust: 89 },
  "Eventbrite": { logo: "/assets/events/sources/eventbrite.svg", trust: 82 },
  "Meetup": { logo: "/assets/events/sources/meetup.svg", trust: 78 },
  "Kültür İstanbul": { logo: "/assets/events/sources/kultur-istanbul.svg", trust: 85 },
  "İBB Kültür Sanat": { logo: "/assets/events/sources/ibb-kultur.svg", trust: 86 },
  "Zorlu PSM": { logo: "/assets/events/sources/zorlu-psm.svg", trust: 88 },
  "AKM İstanbul": { logo: "/assets/events/sources/akm.svg", trust: 88 },
  "Etkinlik.io": { logo: "/assets/events/sources/etkinlikio.svg", trust: 80 },
  "Festivall": { logo: "/assets/events/sources/festivall.svg", trust: 78 },
  "Minika Çocuk": { logo: "/assets/events/sources/minika.svg", trust: 76 },
  "Kültür Yolu Festivali": { logo: "/assets/events/sources/default-event.svg", trust: 84 },
  "AKM Kültür Yolu İstanbul": { logo: "/assets/events/sources/akm.svg", trust: 88 },
  "Kadıköy Kültür Sanat": { logo: "/assets/events/sources/default-event.svg", trust: 82 },
  "İKSV Etkinlikler": { logo: "/assets/events/sources/default-event.svg", trust: 84 },
  "Biletix Blog Güncel": { logo: "/assets/events/sources/biletix.svg", trust: 78 },
  "Biletix Blog Müzik": { logo: "/assets/events/sources/biletix.svg", trust: 78 },
  "Biletix Blog Sanat": { logo: "/assets/events/sources/biletix.svg", trust: 78 },
  "Biletix Blog Aile ve Çocuk": { logo: "/assets/events/sources/biletix.svg", trust: 78 },
};

function getSourceMeta(sourceName = "") {
  if (SOURCE_META[sourceName]) return SOURCE_META[sourceName];
  const value = String(sourceName || "").toLocaleLowerCase("tr-TR");
  if (value.includes("biletix")) return SOURCE_META.Biletix;
  if (value.includes("biletinial")) return SOURCE_META.Biletinial;
  if (value.includes("passo")) return SOURCE_META.Passo;
  if (value.includes("etkinlik.io")) return SOURCE_META["Etkinlik.io"];
  if (value.includes("kültür istanbul") || value.includes("kultur istanbul")) return SOURCE_META["Kültür İstanbul"];
  if (value.includes("ibb") || value.includes("İBB".toLocaleLowerCase("tr-TR"))) return SOURCE_META["İBB Kültür Sanat"];
  if (value.includes("akm")) return SOURCE_META["AKM İstanbul"];
  if (value.includes("zorlu")) return SOURCE_META["Zorlu PSM"];
  return { logo: "/assets/events/sources/default-event.svg", trust: 70 };
}

function slugify(value = "") {
  return String(value)
    .toLocaleLowerCase("tr-TR")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ı/g, "i")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "event";
}

function normalizeText(value = "") {
  return String(value)
    .toLocaleLowerCase("tr-TR")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ı/g, "i")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\b(son dakika|özel|canlı|bilet|etkinlik|konseri|oyunu|festivali)\b/giu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function inferCategory(input = "") {
  const raw = String(input || "");
  for (const [regex, category] of CATEGORY_ALIASES) {
    if (regex.test(raw)) return category;
  }
  return raw && raw !== "Tümü" ? raw : "Etkinlik";
}

function parsePrice(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const n = Number(String(value).replace(/[^0-9.,]/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function normalizeDate(value) {
  const d = value ? new Date(value) : new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  if (!isNaN(d.getTime())) return d.toISOString();
  return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

function createStableId(sourceName, sourceEventId, title, startDate, venueName) {
  const raw = `${sourceName}|${sourceEventId || ""}|${title}|${startDate}|${venueName}`;
  return `${slugify(sourceName)}_${crypto.createHash("sha1").update(raw).digest("hex").slice(0, 12)}`;
}

function getFallbackImage(category) {
  return FALLBACK_IMAGES[category] || FALLBACK_IMAGES.Etkinlik;
}

function normalizeEvent(raw = {}, source = {}) {
  const sourceName = raw.sourceName || source.name || "Smart Events";
  const meta = getSourceMeta(sourceName);
  const category = inferCategory(raw.category || raw.type || raw.tags?.join(" ") || raw.title);
  const startDate = normalizeDate(raw.startDate || raw.date || raw.start || raw.datetime);
  const endDate = raw.endDate ? normalizeDate(raw.endDate) : null;
  const priceMin = parsePrice(raw.priceMin ?? raw.price ?? raw.minPrice);
  const priceMax = parsePrice(raw.priceMax ?? raw.maxPrice ?? priceMin);
  const title = String(raw.title || "Etkinlik").trim();
  const city = String(raw.city || raw.locationCity || process.env.EVENT_CITY || "İstanbul").trim();
  const venueName = String(raw.venueName || raw.venue || raw.place || "Mekan açıklanacak").trim();
  const sourceEventId = raw.sourceEventId || raw.id || raw.url || raw.ticketUrl || title;
  const id = raw.id && String(raw.id).includes("_") ? String(raw.id) : createStableId(sourceName, sourceEventId, title, startDate, venueName);
  const imageUrl = raw.imageUrl || raw.image || raw.thumbnail || getFallbackImage(category);
  const isFree = Boolean(raw.isFree) || priceMin === 0 || /ücretsiz|free/i.test(String(raw.price || raw.description || ""));

  return {
    id,
    title,
    description: String(raw.description || raw.summary || `${title} için güncel etkinlik bilgileri.`).trim(),
    summary: String(raw.summary || raw.description || `${venueName} etkinliği için detay ve bilet bilgileri.`).trim(),
    category,
    startDate,
    endDate,
    date: startDate,
    city,
    district: raw.district || "",
    venueName,
    venue: venueName,
    venueAddress: raw.venueAddress || raw.address || "",
    latitude: raw.latitude ?? null,
    longitude: raw.longitude ?? null,
    priceMin,
    priceMax,
    currency: raw.currency || "TRY",
    ticketUrl: raw.ticketUrl || raw.url || source.url || "",
    sourceName,
    sourceProvider: sourceName,
    sourceLogo: raw.sourceLogo || meta.logo || "/assets/events/sources/default-event.svg",
    sourceEventId: String(sourceEventId),
    imageUrl,
    imageAlt: raw.imageAlt || title,
    imageCredit: raw.imageCredit || sourceName,
    isFree,
    tags: Array.isArray(raw.tags) ? raw.tags : [category, city, sourceName].filter(Boolean),
    popularityScore: Number(raw.popularityScore || meta.trust || 50),
    createdAt: raw.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    sources: []
  };
}

function eventDedupeKey(event) {
  const date = new Date(event.startDate);
  const dayKey = isNaN(date.getTime()) ? "unknown" : date.toISOString().slice(0, 10);
  return [normalizeText(event.title), dayKey, normalizeText(event.venueName), normalizeText(event.city)].join("|");
}

module.exports = {
  SOURCE_META,
  FALLBACK_IMAGES,
  normalizeText,
  inferCategory,
  normalizeEvent,
  eventDedupeKey,
  getFallbackImage,
  slugify,
  getSourceMeta
};
