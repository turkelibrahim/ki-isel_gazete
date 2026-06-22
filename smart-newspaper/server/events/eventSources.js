const EVENT_ADAPTER_SOURCES = [
  { name: "Biletix", type: "html-adapter", url: "https://www.biletix.com/search/TURKIYE/tr", categories: ["konser", "spor", "tiyatro", "sanat", "aile", "müze", "festival"] },
  { name: "Bubilet", type: "html-adapter", url: "https://www.bubilet.com.tr/", categories: ["konser", "tiyatro", "festival", "stand-up"] },
  { name: "Passo", type: "html-sitemap-adapter", url: "https://www.passo.com.tr/", sitemap: "https://www.passo.com.tr/passo_page_sitemap.xml", categories: ["maç", "konser", "tiyatro", "festival"] },
  { name: "Mobilet", type: "html-adapter", url: "https://mobilet.com/all-event-types/", categories: ["konser", "spor", "tiyatro", "festival"] },
  { name: "Biletinial", type: "html-adapter", url: "https://biletinial.com/tr-tr", categories: ["konser", "tiyatro", "sinema", "spor", "festival"] },
  { name: "Kültür İstanbul", type: "html-adapter", url: "https://kultur.istanbul/", categories: ["tiyatro", "konser", "sergi", "çocuk etkinlikleri"] },
  { name: "İBB Kültür Sanat", type: "html-adapter", url: "https://kultursanat.istanbul/etkinliklerimiz", categories: ["konser", "opera", "seminer", "sergi", "söyleşi", "tiyatro"] },
  { name: "Zorlu PSM", type: "html-adapter", url: "https://www.zorlupsm.com/etkinlikler", categories: ["konser", "tiyatro", "müzikal", "sergi"] },
  { name: "AKM İstanbul", type: "html-adapter", url: "https://akmistanbul.gov.tr/tr/etkinlikler", categories: ["konser", "tiyatro", "sergi", "söyleşi", "atölye"] },
  { name: "Ticketmaster", type: "api", url: "https://app.ticketmaster.com/discovery/v2/events.json", envKey: "TICKETMASTER_API_KEY", categories: ["konser", "spor", "tiyatro", "festival"] },
  { name: "Eventbrite", type: "api", url: "https://www.eventbriteapi.com/v3/events/search/", envKey: "EVENTBRITE_API_KEY", categories: ["topluluk", "konser", "festival", "atölye"] },
  { name: "Meetup", type: "api", url: "https://api.meetup.com/", envKey: "MEETUP_API_KEY", categories: ["topluluk", "networking", "teknoloji"] }
];

const EVENT_FEEDS = [
  { name: "Etkinlik.io", type: "rss", url: "https://etkinlik.io/rss/sorgu", note: "Konser, sahne sanatları, festival, sergi, atölye vb. etkinlikleri RSS ile verir." },
  { name: "Etkinlik.io API", type: "api", url: "https://etkinlik.io/api/v2/events", note: "API için token / başvuru gerekir. RSS için kayıt gerekmiyor." },
  { name: "Festivall", type: "rss-json-xml", url: "https://festivall.com.tr/api/v1/", note: "Festival odaklı. RSS / XML / JSON ve Rss 60 Gün bağlantısı var." },
  { name: "Festivall Sitemap", type: "sitemap", url: "https://festivall.com.tr/active-sitemap.xml", note: "Festival detay linklerini toplamak için kullanılabilir." },
  { name: "Minika Çocuk Aktiviteler", type: "rss", url: "https://www.minikacocuk.com.tr/rss/aktiviteler.xml", note: "Çocuk / aile aktiviteleri için kullanılabilir." }
];

module.exports = { EVENT_ADAPTER_SOURCES, EVENT_FEEDS };
