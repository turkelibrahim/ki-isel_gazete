const { sampleEventsForSource } = require("./_sampleEvents");
const { SMART_EVENT_SOURCES, EVENT_CATEGORY_MAP } = require("../eventSources");

const source = {
  name: "Smart Etkinlik Kaynak Kataloğu",
  type: "curated-source-catalog",
  url: "internal://smart-event-sources",
  categories: Object.keys(EVENT_CATEGORY_MAP)
};

function normalizeCategorySlug(slug = "") {
  const value = String(slug || "").toLocaleLowerCase("tr-TR");
  const map = {
    konser: "Konser",
    tiyatro: "Tiyatro",
    sahne_sanatlari: "Tiyatro",
    festival: "Festival",
    sergi: "Sergi",
    sanat: "Sergi",
    atolye: "Atölye",
    egitim: "Atölye",
    fuar: "Fuar",
    spor: "Spor",
    aile_cocuk: "Çocuk",
    cocuk: "Çocuk",
    soylesi: "Söyleşi",
    kultur_sanat: "Kültür Sanat",
    etkinlik_haberleri: "Etkinlik"
  };
  return map[value] || null;
}

function normalizeCitySlug(city = "") {
  const value = String(city || "").toLocaleLowerCase("tr-TR");
  const map = {
    istanbul: "İstanbul",
    ankara: "Ankara",
    izmir: "İzmir",
    antalya: "Antalya",
    bursa: "Bursa",
    mugla: "Muğla",
    muğla: "Muğla",
    eskisehir: "Eskişehir",
    eskişehir: "Eskişehir",
    kocaeli: "Kocaeli",
    all: null
  };
  return map[value] || null;
}

async function fetchEvents(options = {}) {
  const requestedCity = String(options.city || "").toLocaleLowerCase("tr-TR");
  const requestedCategory = String(options.category || options.type || "").toLocaleLowerCase("tr-TR");
  const activeSources = SMART_EVENT_SOURCES
    .filter((item) => item.enabled !== false)
    .filter((item) => {
      if (requestedCity && !["tümü", "tüm kaynaklar", "turkiye", "türkiye", "all"].includes(requestedCity)) {
        const city = String(item.city || "all").toLocaleLowerCase("tr-TR");
        if (city !== "all" && city !== requestedCity) return false;
      }
      if (requestedCategory && !["tümü", "all"].includes(requestedCategory)) {
        const category = normalizeCategorySlug(item.category || "") || String(item.category || "").toLocaleLowerCase("tr-TR");
        if (String(item.category || "all") !== "all" && String(category).toLocaleLowerCase("tr-TR") !== requestedCategory) return false;
      }
      return true;
    });

  return activeSources.flatMap((item) => sampleEventsForSource(item.name).map((event) => ({
    ...event,
    category: normalizeCategorySlug(item.category) || event.category,
    city: normalizeCitySlug(item.city) || event.city,
    sourceName: item.name,
    sourceProvider: item.provider || item.name,
    ticketUrl: item.url || event.ticketUrl,
    tags: [item.provider, item.category, item.city, ...(event.tags || [])].filter(Boolean),
    sourceType: item.type
  })));
}

module.exports = { source, fetchEvents };
