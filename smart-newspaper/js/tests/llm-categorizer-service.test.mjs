import test from "node:test";
import assert from "node:assert/strict";

import llmCategorizerService from "../../services/llmCategorizerService.js";

const {
  ALLOWED_CATEGORIES,
  calculateCost,
  parseAndValidateResponse,
  validateLLMOutput,
  ruleBasedFallback,
  shouldUseLLM,
  categorizeArticle,
  categorizeArticles,
  applyLLMValidationToArticleSync,
  getAdminQueue,
  buildLLMCategorizerStats,
  _internal
} = llmCategorizerService;

test("izinli kategori dışı LLM çıktısı reddedilir", () => {
  const result = validateLLMOutput({ categories: ["Gündem"], confidences: { Gündem: 0.99 }, reasoning: "Yanlış" });
  assert.equal(result.valid, false);
  assert.ok(result.error.includes("İzinsiz"));
});

test("geçerli JSON parse edilir ve tekrar eden kategori tekilleşir", () => {
  const result = parseAndValidateResponse('{"categories":["Teknoloji","Teknoloji"],"confidences":{"Teknoloji":0.94},"reasoning":"AI"}');
  assert.equal(result.valid, true);
  assert.deepEqual(result.output.categories, ["Teknoloji"]);
});

test("JSON olmayan yanıt reddedilir", () => {
  const result = parseAndValidateResponse("Bu haber teknoloji haberidir");
  assert.equal(result.valid, false);
});

test("kural tabanlı fallback Teknoloji + Ekonomi bulur", () => {
  const result = ruleBasedFallback({
    title: "OpenAI yapay zeka yatırımı ve çip ortaklığını duyurdu",
    summary: "Yazılım şirketinin borsa ve yatırım piyasasına etkisi konuşuldu.",
    content: "API, teknoloji, ekonomi, piyasa ve merkez bankası beklentileri öne çıktı."
  });
  assert.ok(result.categories.includes("Teknoloji"));
  assert.ok(result.categories.includes("Ekonomi"));
  assert.ok(Math.max(...Object.values(result.confidences)) <= 0.75);
});

test("belirsiz kısa metin boş kategori döndürür", () => {
  const result = ruleBasedFallback({ title: "Duyuru", summary: "Kısa metin" });
  assert.deepEqual(result.categories, []);
});

test("LLM devreye girme sebepleri doğru hesaplanır", () => {
  assert.deepEqual(shouldUseLLM({ category: "Teknoloji", category_confidence: 0.5, labels: ["Teknoloji"] }), { use: true, trigger_reason: "low_confidence" });
  assert.deepEqual(shouldUseLLM({ category: "Ekonomi", category_confidence: 0.9, labels: ["Teknoloji"] }), { use: true, trigger_reason: "model_conflict" });
});

test("cost hesabı Claude ve OpenAI için doğru çalışır", () => {
  assert.equal(calculateCost("claude", 1000, 100), 0.0045);
  assert.equal(calculateCost("gpt4", 1000, 100), 0.00021);
});

test("API key yoksa categorizeArticle fallback provider ile çalışır", async () => {
  delete process.env.ANTHROPIC_API_KEY;
  delete process.env.OPENAI_API_KEY;
  _internal.responseCache.clear();
  const result = await categorizeArticle({
    id: "n1",
    title: "Futbol maçında üç gol ve transfer gündemi",
    summary: "Spor ve lig haberleri öne çıktı."
  }, { trigger_reason: "manual" });
  assert.equal(result.provider, "fallback");
  assert.ok(result.predicted_labels.includes("Spor"));
});

test("batch 10 haber işlenir", async () => {
  _internal.responseCache.clear();
  const articles = Array.from({ length: 10 }, (_, index) => ({
    id: `t-${index}`,
    title: `OpenAI yapay zeka yazılım haberi ${index}`,
    summary: "Teknoloji, API ve çip gelişmesi."
  }));
  const results = await categorizeArticles(articles, { max_concurrent: 5, trigger_reason: "manual" });
  assert.equal(results.length, 10);
  assert.ok(results.every((item) => item.provider === "fallback"));
});

test("/api/feed payloadına eklenecek llm_validation alanı oluşur", () => {
  const article = applyLLMValidationToArticleSync({
    id: "feed-1",
    title: "Doktor sağlık hastane ve yapay zeka destekli teşhis sistemini duyurdu",
    summary: "Sağlık, tedavi, doktor ve teknoloji alanında yeni sistem hastane kliniklerinde kullanılacak.",
    category: "Sağlık",
    category_confidence: 0.7,
    labels: []
  }, { force: true, trigger_reason: "low_confidence" });
  assert.equal(article.llm_validation.used, true);
  assert.ok(article.llm_validation.predicted_labels.includes("Sağlık"));
  assert.ok(article.labels.includes("Sağlık"));
});

test("admin kuyruğu güvenilmez sonuçları alır", () => {
  const before = getAdminQueue().length;
  applyLLMValidationToArticleSync({ id: "unclear", title: "Kısa duyuru", summary: "Belirsiz" }, { force: true, trigger_reason: "no_label" });
  assert.ok(getAdminQueue().length >= before + 1);
});

test("buildLLMCategorizerStats feed/e-gazete/PDF için özet üretir", () => {
  const article = applyLLMValidationToArticleSync({
    id: "stats-1",
    title: "NASA uzay araştırması ve bilim keşfini açıkladı",
    summary: "Bilim insanları yeni deney sonuçlarını yayımladı."
  }, { force: true, trigger_reason: "manual" });
  const stats = buildLLMCategorizerStats([article]);
  assert.equal(stats.totalArticles, 1);
  assert.ok(stats.validationUsed >= 1);
});

test("izinli kategori listesi 9 kategoridir ve Diğer içermez", () => {
  assert.equal(ALLOWED_CATEGORIES.length, 9);
  assert.equal(ALLOWED_CATEGORIES.includes("Diğer"), false);
  assert.equal(ALLOWED_CATEGORIES.includes("Gündem"), false);
});
