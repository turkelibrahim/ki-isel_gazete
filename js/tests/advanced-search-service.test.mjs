import test from "node:test";
import assert from "node:assert/strict";
import SearchService from "../../services/searchService.js";

function sampleDb() {
  const now = new Date();
  return {
    articles: [
      {
        id: "n1",
        title: "Merkez Bankası faiz kararı ekonomiyi etkiledi",
        summary: "Piyasalar ve dolar hareketlendi.",
        fullText: "Ekonomi yönetimi enflasyon ve faiz kararını değerlendirdi.",
        category: "Ekonomi",
        labels: ["Ekonomi", "Siyaset"],
        sourceName: "TRT Haber",
        publishedAt: now.toISOString(),
        view_count: 20,
        share_count: 4,
        sources: [{ sourceName: "Anadolu Ajansı" }]
      },
      {
        id: "n2",
        title: "Futbol takımından transfer açıklaması",
        summary: "Spor kulübü yeni oyuncuyu duyurdu.",
        fullText: "Lig maçları öncesi transfer tamamlandı.",
        category: "Spor",
        labels: ["Spor"],
        sourceName: "Spor Servisi",
        publishedAt: new Date(now.getTime() - 2 * 86400000).toISOString(),
        view_count: 5,
        share_count: 1
      },
      {
        id: "n3",
        title: "Yapay zeka çipi şirketlerin yatırım planlarını büyüttü",
        summary: "Teknoloji ve ekonomi dünyasında yeni dönem.",
        fullText: "GPU, veri merkezi ve yazılım yatırımları arttı.",
        category: "Teknoloji",
        labels: ["Teknoloji", "Ekonomi"],
        sourceName: "Tekno Günlük",
        publishedAt: new Date(now.getTime() - 3600000).toISOString(),
        view_count: 8,
        share_count: 12
      }
    ],
    searchLogs: [],
    newsInteractions: []
  };
}

test("Türkçe karakter normalize arama çalışır", () => {
  const db = sampleDb();
  const result = SearchService.searchArticles(db, { q: "sirket", limit: 10 }, { log: false });
  assert.equal(result.total, 1);
  assert.equal(result.data[0].id, "n3");
});

test("başlık, özet, içerik ve labels relevance skoru üretir", () => {
  const db = sampleDb();
  const result = SearchService.searchArticles(db, { q: "faiz ekonomi", sort: "relevance" }, { log: false });
  assert.equal(result.data[0].id, "n1");
  assert.ok(result.data[0].score > 0);
});

test("kategori eşleşmesi Politika -> Siyaset map eder", () => {
  const db = sampleDb();
  const result = SearchService.searchArticles(db, { q: "faiz", category: "politika" }, { log: false });
  assert.equal(result.total, 1);
  assert.equal(result.data[0].id, "n1");
});

test("kaynak filtresi cluster içindeki kaynağı dikkate alır", () => {
  const db = sampleDb();
  const result = SearchService.searchArticles(db, { q: "faiz", source: "Anadolu Ajansı" }, { log: false });
  assert.equal(result.total, 1);
  assert.equal(result.data[0].id, "n1");
});

test("sort most_read ve most_shared çalışır", () => {
  const db = sampleDb();
  const mostRead = SearchService.searchArticles(db, { q: "", sort: "most_read" }, { log: false });
  assert.equal(mostRead.data[0].id, "n1");
  const mostShared = SearchService.searchArticles(db, { q: "", sort: "most_shared" }, { log: false });
  assert.equal(mostShared.data[0].id, "n3");
});

test("dateFilter today sadece bugünün haberlerini getirir", () => {
  const db = sampleDb();
  const result = SearchService.searchArticles(db, { q: "", dateFilter: "today", limit: 10 }, { log: false });
  assert.ok(result.data.every((item) => item.id !== "n2"));
});

test("arama logu ve search click interaction kaydedilir", () => {
  const db = sampleDb();
  SearchService.searchArticles(db, { q: "ekonomi" }, { userId: "u1" });
  assert.equal(db.searchLogs.length, 1);
  SearchService.recordNewsInteraction(db, "n1", "u1", "search_click");
  assert.equal(db.newsInteractions.length, 1);
  assert.equal(db.articles[0].search_click_count, 1);
  assert.equal(db.searchLogs[0].clicked_news_id, "n1");
});

test("trend skoru etkileşimlerden hesaplanır", () => {
  const db = sampleDb();
  SearchService.recordNewsInteraction(db, "n1", "u1", "view");
  SearchService.recordNewsInteraction(db, "n1", "u1", "share");
  const trends = SearchService.getTrends(db, { limit: 3 });
  assert.ok(trends.data[0].trend_score >= 0);
  assert.ok(trends.data.some((item) => item.id === "n1"));
});

test("çok uzun query güvenli şekilde kısalır", () => {
  const query = "a".repeat(300);
  assert.equal(SearchService.sanitizeQuery(query).length, SearchService.MAX_QUERY_LENGTH);
});
