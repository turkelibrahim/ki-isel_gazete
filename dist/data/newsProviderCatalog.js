// SmartNewspaper Türkiye haber kaynakları ve API provider katalogları.
export const NEWS_API_PROVIDERS = [
  {
    "name": "GNews",
    "type": "api",
    "endpoint": "https://gnews.io/api/v4/top-headlines?country=tr&category=general&apikey=GNEWS_API_KEY",
    "envKey": "GNEWS_API_KEY",
    "notes": "Türkiye genel haberleri için iyi fallback."
  },
  {
    "name": "NewsAPI",
    "type": "api",
    "endpoint": "https://newsapi.org/v2/top-headlines?country=tr&apiKey=NEWS_API_KEY",
    "envKey": "NEWS_API_KEY",
    "notes": "Top headlines için kullanılabilir; plan limitlerini kontrol et."
  },
  {
    "name": "Mediastack",
    "type": "api",
    "endpoint": "http://api.mediastack.com/v1/news?access_key=MEDIASTACK_API_KEY&countries=tr&languages=tr",
    "envKey": "MEDIASTACK_API_KEY",
    "notes": "Türkiye, kategori ve dil filtreleri için kullanılabilir."
  },
  {
    "name": "World News API",
    "type": "api",
    "endpoint": "https://api.worldnewsapi.com/top-news?source-country=tr&api-key=WORLD_NEWS_API_KEY",
    "envKey": "WORLD_NEWS_API_KEY",
    "notes": "Türkiye kaynaklı haberleri çekmek için alternatif."
  },
  {
    "name": "Event Registry / NewsAPI.ai",
    "type": "api",
    "endpoint": "https://eventregistry.org/api/v1/article/getArticles",
    "envKey": "EVENT_REGISTRY_API_KEY",
    "notes": "Trend, olay kümeleme, kaynak analizi için güçlü."
  }
];

export const TURKEY_NEWS_SOURCES = [
  {
    "name": "TRT Haber",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.trthaber.com/sondakika_articles.rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:trthaber.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "TRT Haber Gündem",
    "type": "rss",
    "category": "gundem",
    "directRss": "https://www.trthaber.com/gundem_articles.rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:trthaber.com/gundem&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "A Haber",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.ahaber.com.tr/rss/tum-mansetler.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:ahaber.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "A Haber Ekonomi",
    "type": "rss",
    "category": "ekonomi",
    "directRss": "https://www.ahaber.com.tr/rss/ekonomi.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:ahaber.com.tr/ekonomi&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Sözcü",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.sozcu.com.tr/feeds-haberler",
    "fallbackRss": "https://news.google.com/rss/search?q=site:sozcu.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Sözcü Son Dakika",
    "type": "rss",
    "category": "son_dakika",
    "directRss": "https://www.sozcu.com.tr/feeds-son-dakika",
    "fallbackRss": "https://news.google.com/rss/search?q=site:sozcu.com.tr%20son%20dakika&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Sözcü Gündem",
    "type": "rss",
    "category": "gundem",
    "directRss": "https://www.sozcu.com.tr/feeds-rss-category-gundem",
    "fallbackRss": "https://news.google.com/rss/search?q=site:sozcu.com.tr/gundem&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Habertürk",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.haberturk.com/rss/anasayfa",
    "fallbackRss": "https://news.google.com/rss/search?q=site:haberturk.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Habertürk Son Dakika",
    "type": "rss",
    "category": "son_dakika",
    "directRss": "https://www.haberturk.com/rss/sondakika",
    "fallbackRss": "https://news.google.com/rss/search?q=site:haberturk.com%20son%20dakika&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Haberler.com",
    "type": "rss",
    "category": "genel",
    "directRss": "https://rss.haberler.com/rss.asp",
    "fallbackRss": "https://news.google.com/rss/search?q=site:haberler.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Ensonhaber",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:ensonhaber.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Ensonhaber Gündem",
    "type": "rss",
    "category": "gundem",
    "directRss": "https://www.ensonhaber.com/rss/gundem.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:ensonhaber.com/gundem&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Takvim",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.takvim.com.tr/rss/news.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:takvim.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Takvim Ekonomi",
    "type": "rss",
    "category": "ekonomi",
    "directRss": "https://www.takvim.com.tr/rss/ekonomi",
    "fallbackRss": "https://news.google.com/rss/search?q=site:takvim.com.tr/ekonomi&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Yeni Şafak",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.yenisafak.com/rss-feeds?take=60",
    "fallbackRss": "https://news.google.com/rss/search?q=site:yenisafak.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "İhlas Haber Ajansı",
    "type": "rss",
    "category": "ajans",
    "directRss": "https://www.iha.com.tr/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:iha.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Anadolu Ajansı Teyit Hattı",
    "type": "rss",
    "category": "teyit",
    "directRss": "https://www.aa.com.tr/tr/teyithatti/rss/news?cat=0",
    "fallbackRss": "https://news.google.com/rss/search?q=site:aa.com.tr/tr/teyithatti&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Anadolu Ajansı Teyit Ekonomi",
    "type": "rss",
    "category": "ekonomi",
    "directRss": "https://www.aa.com.tr/tr/teyithatti/rss/news?cat=ekonomi",
    "fallbackRss": "https://news.google.com/rss/search?q=site:aa.com.tr/tr/teyithatti%20ekonomi&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "CNN Türk",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.cnnturk.com/feed/rss/all/news",
    "fallbackRss": "https://news.google.com/rss/search?q=site:cnnturk.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "NTV",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.ntv.com.tr/gundem.rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:ntv.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Hürriyet",
    "type": "rss_or_google_news",
    "category": "genel",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:hurriyet.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Milliyet",
    "type": "rss_or_google_news",
    "category": "genel",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:milliyet.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Sabah",
    "type": "rss_or_google_news",
    "category": "genel",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:sabah.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Posta",
    "type": "rss_or_google_news",
    "category": "genel",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:posta.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Cumhuriyet",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.cumhuriyet.com.tr/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:cumhuriyet.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Karar",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.karar.com/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:karar.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "T24",
    "type": "rss",
    "category": "genel",
    "directRss": "https://t24.com.tr/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:t24.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Diken",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.diken.com.tr/feed/",
    "fallbackRss": "https://news.google.com/rss/search?q=site:diken.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Gazete Duvar",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.gazeteduvar.com.tr/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:gazeteduvar.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "BirGün",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.birgun.net/rss/home",
    "fallbackRss": "https://news.google.com/rss/search?q=site:birgun.net&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Evrensel",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.evrensel.net/rss.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:evrensel.net&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Odatv",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.odatv.com/rss.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:odatv.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Halk TV",
    "type": "rss",
    "category": "genel",
    "directRss": "https://halktv.com.tr/rss.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:halktv.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Medyascope",
    "type": "rss",
    "category": "genel",
    "directRss": "https://medyascope.tv/feed/",
    "fallbackRss": "https://news.google.com/rss/search?q=site:medyascope.tv&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Artı Gerçek",
    "type": "rss",
    "category": "genel",
    "directRss": "https://artigercek.com/service/rss.php",
    "fallbackRss": "https://news.google.com/rss/search?q=site:artigercek.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Aydınlık",
    "type": "rss",
    "category": "genel",
    "directRss": "https://www.aydinlik.com.tr/feed",
    "fallbackRss": "https://news.google.com/rss/search?q=site:aydinlik.com.tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Bianet",
    "type": "rss",
    "category": "genel",
    "directRss": "https://bianet.org/biamag.rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:bianet.org&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Dokuz8 Haber",
    "type": "rss",
    "category": "genel",
    "directRss": "https://dokuz8haber.net/rss.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:dokuz8haber.net&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Dünya Gazetesi",
    "type": "rss",
    "category": "ekonomi",
    "directRss": "https://www.dunya.com/rss?dunya",
    "fallbackRss": "https://news.google.com/rss/search?q=site:dunya.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Bloomberg HT",
    "type": "rss_or_google_news",
    "category": "ekonomi",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:bloomberght.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "BBC Türkçe",
    "type": "rss",
    "category": "uluslararasi_tr",
    "directRss": "https://feeds.bbci.co.uk/turkce/rss.xml",
    "fallbackRss": "https://news.google.com/rss/search?q=site:bbc.com/turkce&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "DW Türkçe",
    "type": "rss",
    "category": "uluslararasi_tr",
    "directRss": "https://rss.dw.com/rdf/rss-tur-all",
    "fallbackRss": "https://news.google.com/rss/search?q=site:dw.com/tr&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Euronews Türkçe",
    "type": "rss_or_mrss",
    "category": "uluslararasi_tr",
    "directRss": "https://tr.euronews.com/rss",
    "fallbackRss": "https://news.google.com/rss/search?q=site:tr.euronews.com&hl=tr&gl=TR&ceid=TR:tr"
  },
  {
    "name": "Independent Türkçe",
    "type": "rss_or_google_news",
    "category": "uluslararasi_tr",
    "directRss": null,
    "fallbackRss": "https://news.google.com/rss/search?q=site:indyturk.com&hl=tr&gl=TR&ceid=TR:tr"
  }
];

export const SOURCE_META = {
  "trt_haber": {
    "name": "TRT Haber",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 86
  },
  "sozcu": {
    "name": "Sözcü",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 78
  },
  "ntv": {
    "name": "NTV",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 82
  },
  "cnnturk": {
    "name": "CNN Türk",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 80
  },
  "haberturk": {
    "name": "Habertürk",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 81
  },
  "hurriyet": {
    "name": "Hürriyet",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 79
  },
  "milliyet": {
    "name": "Milliyet",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 78
  },
  "sabah": {
    "name": "Sabah",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 78
  },
  "cumhuriyet": {
    "name": "Cumhuriyet",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 79
  },
  "karar": {
    "name": "Karar",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 76
  },
  "t24": {
    "name": "T24",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 77
  },
  "diken": {
    "name": "Diken",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 76
  },
  "dunya_gazetesi": {
    "name": "Dünya Gazetesi",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 84
  },
  "bloomberg_ht": {
    "name": "Bloomberg HT",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 84
  },
  "bbc_turkce": {
    "name": "BBC Türkçe",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 85
  },
  "dw_turkce": {
    "name": "DW Türkçe",
    "icon": "/assets/sources/default-news.svg",
    "trustScore": 84
  }
};

export const DEFAULT_SOURCE_ICON = '/assets/sources/default-news.svg';
