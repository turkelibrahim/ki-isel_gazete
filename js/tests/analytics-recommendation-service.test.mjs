import test from "node:test";
import assert from "node:assert/strict";
import AnalyticsService from "../../services/analyticsService.js";
import RecommendationService from "../../services/recommendationService.js";
import VectorService from "../../services/vectorService.js";

function demoDb() {
  const now = Date.now();
  return {
    articles: [
      {
        id: "n1",
        title: "Merkez Bankası faiz kararını açıkladı",
        summary: "Ekonomi, enflasyon ve piyasa beklentileri öne çıktı.",
        content: "Borsa, yatırım ve banka haberleri ekonomi gündeminde.",
        category: "Ekonomi",
        labels: ["Ekonomi"],
        tags: ["faiz", "borsa", "yatırım"],
        source_name: "Sabah",
        published_at: new Date(now - 2 * 3600000).toISOString(),
        view_count: 50,
        share_count: 10,
        sources: [{ sourceName: "Sabah" }]
      },
      {
        id: "n2",
        title: "Yapay zeka çipleri yeni dönemi başlatıyor",
        summary: "Teknoloji şirketleri GPU ve yazılım yatırımlarını artırıyor.",
        content: "Yapay zeka, siber güvenlik ve veri merkezi yatırımları hızlandı.",
        category: "Teknoloji",
        labels: ["Teknoloji", "Bilim"],
        tags: ["yapay zeka", "çip", "yazılım"],
        source_name: "TRT Haber",
        published_at: new Date(now - 4 * 3600000).toISOString(),
        view_count: 100,
        share_count: 20,
        sources: [{ sourceName: "TRT Haber" }]
      },
      {
        id: "n3",
        title: "Borsa teknoloji hisseleriyle yükseldi",
        summary: "Ekonomi piyasalarında teknoloji şirketleri öne çıktı.",
        content: "Yatırımcılar yapay zeka ve çip şirketlerini takip ediyor.",
        category: "Ekonomi",
        labels: ["Ekonomi", "Teknoloji"],
        tags: ["borsa", "teknoloji", "yatırım"],
        source_name: "Piyasa Notları",
        published_at: new Date(now - 6 * 3600000).toISOString(),
        view_count: 20,
        share_count: 4,
        sources: [{ sourceName: "Piyasa Notları" }]
      }
    ],
    userSessions: [],
    userInteractions: [],
    userProfiles: [],
    userRecommendations: [],
    newsVectors: []
  };
}

test("analytics track creates session, interaction and updates profile", () => {
  const db = demoDb();
  const result = AnalyticsService.trackInteraction(db, {
    session_id: "sess-test",
    news_id: "n1",
    interaction_type: "read",
    duration_seconds: 92
  }, { userId: "u1", anonymousId: "a1" });
  assert.equal(result.success, true);
  assert.equal(db.userSessions.length, 1);
  assert.equal(db.userInteractions.length, 1);
  assert.equal(db.userProfiles.length, 1);
  assert.equal(db.userProfiles[0].favorite_categories_json.Ekonomi > 0, true);
  assert.equal(db.userProfiles[0].total_reading_time, 92);
});

test("invalid interaction type is rejected", () => {
  const db = demoDb();
  assert.throws(() => AnalyticsService.trackInteraction(db, {
    news_id: "n1",
    interaction_type: "hack"
  }, { userId: "u1" }), /Geçersiz interaction_type/);
});

test("TF-IDF vectors and cosine similarity work with Turkish text", () => {
  const db = demoDb();
  const model = VectorService.buildTfidfModel(db.articles);
  const sim = VectorService.cosineSimilarity(model.vectors.get("n1"), model.vectors.get("n3"));
  assert.equal(model.vocabularySize > 0, true);
  assert.equal(sim > 0, true);
  assert.equal(VectorService.normalizeTurkishAscii("şirket gündem Türkiye"), "sirket gundem turkiye");
});

test("content based recommendations exclude read articles and rank similar news", () => {
  const db = demoDb();
  AnalyticsService.trackInteraction(db, {
    session_id: "sess-test",
    news_id: "n1",
    interaction_type: "read",
    duration_seconds: 120
  }, { userId: "u1", anonymousId: "a1" });
  const payload = RecommendationService.computeContentBased(db, { userId: "u1", anonymousId: "a1", limit: 5 });
  assert.equal(payload.success, true);
  assert.equal(payload.data.some((item) => item.news_id === "n1"), false);
  assert.equal(payload.data.length > 0, true);
  assert.equal(typeof payload.data[0].reason, "string");
});

test("hybrid recommendations cold-start fallback returns popular fresh news", () => {
  const db = demoDb();
  const payload = RecommendationService.computeHybrid(db, { userId: "new-user", anonymousId: "anon-new", limit: 2 });
  assert.equal(payload.success, true);
  assert.equal(payload.data.length, 2);
  assert.equal(payload.algorithm, "cold_start_trending_recent");
});

test("feedback marks recommendation as dismissed", () => {
  const db = demoDb();
  RecommendationService.computeHybrid(db, { userId: "u1", anonymousId: "a1", limit: 2 });
  const target = db.userRecommendations[0];
  const result = RecommendationService.applyFeedback(db, { userId: "u1", anonymousId: "a1", newsId: target.news_id, feedback: "not_interested" });
  assert.equal(result.success, true);
  assert.equal(db.userRecommendations.find((item) => item.news_id === target.news_id).status, "dismissed");
});

test("dashboard summarizes real interactions", () => {
  const db = demoDb();
  AnalyticsService.trackInteraction(db, { session_id: "s", news_id: "n1", interaction_type: "read", duration_seconds: 60 }, { userId: "u1", anonymousId: "a1" });
  AnalyticsService.trackInteraction(db, { session_id: "s", news_id: "n2", interaction_type: "share", duration_seconds: 0 }, { userId: "u1", anonymousId: "a1" });
  const dashboard = AnalyticsService.buildDashboard(db, { userId: "u1", anonymousId: "a1" });
  assert.equal(dashboard.success, true);
  assert.equal(dashboard.summary.total_articles_read >= 1, true);
  assert.equal(dashboard.summary.total_reading_time_minutes, 1);
  assert.equal(dashboard.top_categories.length > 0, true);
});

test("exclude read fallback does not empty recommendation list when every article was read", () => {
  const db = demoDb();
  for (const article of db.articles) {
    AnalyticsService.trackInteraction(db, {
      session_id: "sess-all-read",
      news_id: article.id,
      interaction_type: "read",
      duration_seconds: 30
    }, { userId: "u-read-all", anonymousId: "a-read-all" });
  }
  const payload = RecommendationService.computeHybrid(db, { userId: "u-read-all", anonymousId: "a-read-all", limit: 3, excludeRead: true });
  assert.equal(payload.success, true);
  assert.equal(payload.data.length > 0, true);
  assert.equal(payload.count > 0, true);
});

test("recommendation feedback creates dismissal record even when recommendation row is missing", () => {
  const db = demoDb();
  const result = RecommendationService.applyFeedback(db, { userId: "u-missing-rec", anonymousId: "a-missing-rec", newsId: "n2", feedback: "not_interested" });
  assert.equal(result.success, true);
  const saved = db.userRecommendations.find((item) => item.news_id === "n2" && item.user_id === "u-missing-rec");
  assert.equal(saved.status, "dismissed");
  const payload = RecommendationService.computeHybrid(db, { userId: "u-missing-rec", anonymousId: "a-missing-rec", limit: 3 });
  assert.equal(payload.data.some((item) => item.news_id === "n2"), false);
});
