const EVENT_RSS_SOURCES = [
  { name: "Etkinlik.io Tüm Etkinlikler", type: "rss", provider: "etkinlik.io", category: "all", city: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true }
];

const EVENT_IO_RSS_VIRTUAL_SOURCES = [
  { name: "Etkinlik.io İstanbul", type: "rss", provider: "etkinlik.io", city: "istanbul", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Ankara", type: "rss", provider: "etkinlik.io", city: "ankara", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io İzmir", type: "rss", provider: "etkinlik.io", city: "izmir", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Antalya", type: "rss", provider: "etkinlik.io", city: "antalya", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Bursa", type: "rss", provider: "etkinlik.io", city: "bursa", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Muğla", type: "rss", provider: "etkinlik.io", city: "mugla", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Eskişehir", type: "rss", provider: "etkinlik.io", city: "eskisehir", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Kocaeli", type: "rss", provider: "etkinlik.io", city: "kocaeli", category: "all", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Konser", type: "rss", provider: "etkinlik.io", city: "all", category: "konser", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Tiyatro / Sahne Sanatları", type: "rss", provider: "etkinlik.io", city: "all", category: "sahne_sanatlari", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Festival", type: "rss", provider: "etkinlik.io", city: "all", category: "festival", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Sergi", type: "rss", provider: "etkinlik.io", city: "all", category: "sergi", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Atölye", type: "rss", provider: "etkinlik.io", city: "all", category: "atolye", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Fuar", type: "rss", provider: "etkinlik.io", city: "all", category: "fuar", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Eğitim", type: "rss", provider: "etkinlik.io", city: "all", category: "egitim", url: "https://etkinlik.io/rss/sorgu", enabled: true },
  { name: "Etkinlik.io Söyleşi", type: "rss", provider: "etkinlik.io", city: "all", category: "soylesi", url: "https://etkinlik.io/rss/sorgu", enabled: true }
];

const EVENT_HTML_SOURCES = [
  { name: "Biletix Türkiye", type: "html", provider: "biletix", category: "all", city: "all", url: "https://www.biletix.com/search/TURKIYE/tr", enabled: true },
  { name: "Biletix İstanbul", type: "html", provider: "biletix", category: "all", city: "istanbul", url: "https://www.biletix.com/anasayfa/ISTANBUL/tr", enabled: true },
  { name: "Biletix Müzik", type: "html", provider: "biletix", category: "konser", city: "all", url: "https://www.biletix.com/search/MUSIC/TURKIYE/tr", enabled: true },
  { name: "Biletix Sanat", type: "html", provider: "biletix", category: "sanat", city: "all", url: "https://www.biletix.com/search/ARTS/TURKIYE/tr", enabled: true },
  { name: "Biletix Spor", type: "html", provider: "biletix", category: "spor", city: "all", url: "https://www.biletix.com/search/SPORTS/TURKIYE/tr", enabled: true },
  { name: "Biletix Aile ve Çocuk", type: "html", provider: "biletix", category: "aile_cocuk", city: "all", url: "https://www.biletix.com/search/FAMILY/TURKIYE/tr", enabled: true },
  { name: "Biletinial Türkiye", type: "html", provider: "biletinial", category: "all", city: "all", url: "https://biletinial.com/tr-tr", enabled: true },
  { name: "Biletinial Ankara Etkinlikleri", type: "html", provider: "biletinial", category: "all", city: "ankara", url: "https://biletinial.com/tr-tr/etkinlikleri/ankara-etkinlikler", enabled: true },
  { name: "Biletinial Kültür Yolu Festivalleri", type: "html", provider: "biletinial", category: "festival", city: "all", url: "https://biletinial.com/tr-tr/etkinlikleri/turkiye-kultur-yolu-festivalleri", enabled: true },
  { name: "Passo Türkiye", type: "html", provider: "passo", category: "all", city: "all", url: "https://www.passo.com.tr/", enabled: true },
  { name: "Kültür Yolu Festivali", type: "html", provider: "kultur_yolu", category: "festival", city: "all", url: "https://kulturyolufestivali.com/", enabled: true },
  { name: "AKM Kültür Yolu İstanbul", type: "html", provider: "akm", category: "festival", city: "istanbul", url: "https://www.akmistanbul.gov.tr/tr/turkiye-kultur-yolu-festivali-istanbul", enabled: true },
  { name: "Kültür İstanbul Etkinlik Takvimi", type: "html", provider: "kultur_istanbul", category: "kultur_sanat", city: "istanbul", url: "https://kultur.istanbul/etkinlikler/", enabled: true },
  { name: "İBB Kültür Sanat Etkinlikleri", type: "html", provider: "ibb_kultur_sanat", category: "kultur_sanat", city: "istanbul", url: "https://kultursanat.istanbul/etkinliklerimiz", enabled: true },
  { name: "İBB Etkinlikler", type: "html", provider: "ibb", category: "belediye_etkinlikleri", city: "istanbul", url: "https://ibb.istanbul/gundem/etkinlikler/", enabled: true },
  { name: "Kadıköy Kültür Sanat", type: "html", provider: "kadikoy_kultur_sanat", category: "kultur_sanat", city: "istanbul", url: "https://kultursanat.kadikoy.bel.tr/tr/kadikoyde-kultur-sanat", enabled: true },
  { name: "İKSV Etkinlikler", type: "html", provider: "iksv", category: "kultur_sanat", city: "istanbul", url: "https://www.iksv.org/tr/etkinlikler/etkinlikler", enabled: true }
];

const EVENT_BLOG_SOURCES = [
  { name: "Biletix Blog Güncel", type: "html", provider: "biletix_blog", category: "etkinlik_haberleri", city: "all", url: "https://blog.biletix.com/guncel", enabled: true },
  { name: "Biletix Blog Müzik", type: "html", provider: "biletix_blog", category: "konser", city: "all", url: "https://blog.biletix.com/muzik", enabled: true },
  { name: "Biletix Blog Sanat", type: "html", provider: "biletix_blog", category: "sanat", city: "all", url: "https://blog.biletix.com/sanat", enabled: true },
  { name: "Biletix Blog Aile ve Çocuk", type: "html", provider: "biletix_blog", category: "aile_cocuk", city: "all", url: "https://blog.biletix.com/aile-ve-cocuk", enabled: true }
];

const LEGACY_EVENT_ADAPTER_SOURCES = [
  { name: "Biletix", type: "html-adapter", provider: "biletix", city: "all", category: "all", url: "https://www.biletix.com/search/TURKIYE/tr", enabled: true, categories: ["konser", "spor", "tiyatro", "sanat", "aile", "müze", "festival"] },
  { name: "Bubilet", type: "html-adapter", provider: "bubilet", city: "all", category: "all", url: "https://www.bubilet.com.tr/", enabled: true, categories: ["konser", "tiyatro", "festival", "stand-up"] },
  { name: "Passo", type: "html-sitemap-adapter", provider: "passo", city: "all", category: "all", url: "https://www.passo.com.tr/", sitemap: "https://www.passo.com.tr/passo_page_sitemap.xml", enabled: true, categories: ["maç", "konser", "tiyatro", "festival"] },
  { name: "Mobilet", type: "html-adapter", provider: "mobilet", city: "all", category: "all", url: "https://mobilet.com/all-event-types/", enabled: true, categories: ["konser", "spor", "tiyatro", "festival"] },
  { name: "Biletinial", type: "html-adapter", provider: "biletinial", city: "all", category: "all", url: "https://biletinial.com/tr-tr", enabled: true, categories: ["konser", "tiyatro", "sinema", "spor", "festival"] },
  { name: "Kültür İstanbul", type: "html-adapter", provider: "kultur_istanbul", city: "istanbul", category: "kultur_sanat", url: "https://kultur.istanbul/etkinlikler/", enabled: true, categories: ["tiyatro", "konser", "sergi", "çocuk etkinlikleri"] },
  { name: "İBB Kültür Sanat", type: "html-adapter", provider: "ibb_kultur_sanat", city: "istanbul", category: "kultur_sanat", url: "https://kultursanat.istanbul/etkinliklerimiz", enabled: true, categories: ["konser", "opera", "seminer", "sergi", "söyleşi", "tiyatro"] },
  { name: "Zorlu PSM", type: "html-adapter", provider: "zorlu_psm", city: "istanbul", category: "kultur_sanat", url: "https://www.zorlupsm.com/etkinlikler", enabled: true, categories: ["konser", "tiyatro", "müzikal", "sergi"] },
  { name: "AKM İstanbul", type: "html-adapter", provider: "akm", city: "istanbul", category: "kultur_sanat", url: "https://akmistanbul.gov.tr/tr/etkinlikler", enabled: true, categories: ["konser", "tiyatro", "sergi", "söyleşi", "atölye"] },
  { name: "Ticketmaster", type: "api", provider: "ticketmaster", city: "all", category: "all", url: "https://app.ticketmaster.com/discovery/v2/events.json", envKey: "TICKETMASTER_API_KEY", enabled: true, categories: ["konser", "spor", "tiyatro", "festival"] },
  { name: "Eventbrite", type: "api", provider: "eventbrite", city: "all", category: "all", url: "https://www.eventbriteapi.com/v3/events/search/", envKey: "EVENTBRITE_API_KEY", enabled: true, categories: ["topluluk", "konser", "festival", "atölye"] },
  { name: "Meetup", type: "api", provider: "meetup", city: "all", category: "all", url: "https://api.meetup.com/", envKey: "MEETUP_API_KEY", enabled: true, categories: ["topluluk", "networking", "teknoloji"] },
  { name: "Festivall", type: "rss-json-xml", provider: "festivall", city: "all", category: "festival", url: "https://festivall.com.tr/api/v1/", enabled: true, categories: ["festival"] },
  { name: "Minika Çocuk", type: "rss", provider: "minika", city: "all", category: "aile_cocuk", url: "https://www.minikacocuk.com.tr/rss/aktiviteler.xml", enabled: true, categories: ["çocuk", "aile"] }
];

const EVENT_CATEGORY_MAP = {
  konser: ["konser", "müzik", "music", "canlı müzik", "festival konser"],
  tiyatro: ["tiyatro", "sahne sanatları", "oyun", "stand up", "komedi"],
  festival: ["festival", "kültür yolu", "beyoğlu kültür yolu", "caz festivali"],
  sergi: ["sergi", "müze", "galeri", "bienal", "dijital sanat"],
  atolye: ["atölye", "workshop", "eğitim", "çocuk atölyesi"],
  fuar: ["fuar", "expo", "festival alanı"],
  spor: ["maç", "spor", "basketbol", "futbol", "voleybol"],
  aile_cocuk: ["çocuk", "aile", "çocuk tiyatrosu", "masal", "müzikal"],
  soylesi: ["söyleşi", "panel", "konferans", "seminer"],
  kultur_sanat: ["kültür", "sanat", "opera", "bale", "klasik müzik"]
};

function sourceKey(source = {}) {
  return [source.name, source.provider, source.city || "all", source.category || "all", source.url].join("|").toLocaleLowerCase("tr-TR");
}

function dedupeSources(sources) {
  const seen = new Set();
  return sources.filter((source) => {
    const key = sourceKey(source);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const SMART_EVENT_SOURCES = dedupeSources([
  ...EVENT_RSS_SOURCES,
  ...EVENT_IO_RSS_VIRTUAL_SOURCES,
  ...EVENT_HTML_SOURCES,
  ...EVENT_BLOG_SOURCES,
  ...LEGACY_EVENT_ADAPTER_SOURCES
]);

const EVENT_ADAPTER_SOURCES = LEGACY_EVENT_ADAPTER_SOURCES;

const EVENT_FEEDS = [
  ...EVENT_RSS_SOURCES,
  ...EVENT_IO_RSS_VIRTUAL_SOURCES,
  { name: "Festivall", type: "rss-json-xml", provider: "festivall", category: "festival", city: "all", url: "https://festivall.com.tr/api/v1/", enabled: true, note: "Festival odaklı XML/JSON/RSS kaynağı." },
  { name: "Festivall Sitemap", type: "sitemap", provider: "festivall", category: "festival", city: "all", url: "https://festivall.com.tr/active-sitemap.xml", enabled: true, note: "Festival detay linklerini toplamak için kullanılabilir." },
  { name: "Minika Çocuk Aktiviteler", type: "rss", provider: "minika", category: "aile_cocuk", city: "all", url: "https://www.minikacocuk.com.tr/rss/aktiviteler.xml", enabled: true, note: "Çocuk / aile aktiviteleri için kullanılabilir." }
];

function getEventSourceSummary() {
  const byType = {};
  const byProvider = {};
  const cities = new Set(["all"]);
  const categories = new Set(["all"]);
  for (const source of SMART_EVENT_SOURCES) {
    byType[source.type] = (byType[source.type] || 0) + 1;
    byProvider[source.provider || source.name] = (byProvider[source.provider || source.name] || 0) + 1;
    if (source.city) cities.add(source.city);
    if (source.category) categories.add(source.category);
  }
  return {
    total: SMART_EVENT_SOURCES.length,
    byType,
    byProvider,
    cities: [...cities].sort(),
    categories: [...categories].sort()
  };
}

module.exports = {
  EVENT_RSS_SOURCES,
  EVENT_IO_RSS_VIRTUAL_SOURCES,
  EVENT_HTML_SOURCES,
  EVENT_BLOG_SOURCES,
  EVENT_CATEGORY_MAP,
  EVENT_ADAPTER_SOURCES,
  EVENT_FEEDS,
  SMART_EVENT_SOURCES,
  getEventSourceSummary
};
