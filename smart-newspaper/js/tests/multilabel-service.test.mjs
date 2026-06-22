import test from "node:test";
import assert from "node:assert/strict";

import {
  ALLOWED_LABELS,
  FORBIDDEN_LABELS,
  classifyArticleLabels,
  classifyArticlesLabels,
  validatePrediction,
  applyMultilabelToArticle,
  groupArticlesByLabel,
  buildMultilabelStats
} from "../../services/multilabelService.js";

test("Teknoloji + Ekonomi haberi iki etiket alır", () => {
  const result = classifyArticleLabels({
    title: "OpenAI yapay zeka yatırımı ve yeni API hamlesi borsayı etkiledi",
    summary: "Teknoloji şirketleri, çip üreticileri ve ekonomi piyasaları yatırım haberine tepki verdi.",
    content: "Yazılım, startup, piyasa, borsa ve merkez bankası etkisi aynı haberde yer aldı."
  });
  assert.ok(result.labels.includes("Teknoloji"));
  assert.ok(result.labels.includes("Ekonomi"));
  assert.equal(result.label_vector[ALLOWED_LABELS.indexOf("Teknoloji")], 1);
  assert.equal(result.label_vector[ALLOWED_LABELS.indexOf("Ekonomi")], 1);
  assert.equal(result.num_labels, 9);
});

test("Spor haberi sadece Spor etiketi alır", () => {
  const result = classifyArticleLabels({
    title: "Galatasaray derbide Fenerbahçe karşısında üç golle kazandı",
    summary: "Süper Lig maçında futbol ve transfer gündemi değişti."
  });
  assert.deepEqual(result.labels, ["Spor"]);
});

test("Hiçbir skor eşiği geçmezse boş liste döner", () => {
  const result = classifyArticleLabels({ title: "Mahallede yeni düzenleme", summary: "Kısa ve belirsiz bir haber metni." });
  assert.deepEqual(result.labels, []);
  assert.equal(result.no_label_detected, true);
  assert.equal(result.fallback_category, "Diğer");
});

test("Gündem, Diğer, Genel ve Bilinmeyen asla üretilmez", () => {
  const result = classifyArticleLabels({ title: "Son dakika gündem genel bilinmeyen haber", summary: "Diğer etiketi üretilmemeli." });
  for (const label of FORBIDDEN_LABELS) assert.equal(result.labels.includes(label), false);
  assert.deepEqual(Object.keys(result.label_scores), ALLOWED_LABELS);
});

test("İzinli olmayan etiket validator tarafından reddedilir", () => {
  const result = validatePrediction({
    labels: ["Teknoloji", "Gündem", "Genel"],
    label_scores: { Teknoloji: 0.91, Gündem: 0.99 },
    is_multilabel_reliable: true
  });
  assert.deepEqual(result.labels, ["Teknoloji"]);
  assert.ok(result.rejected_labels.includes("Gündem"));
  assert.ok(result.rejected_labels.includes("Genel"));
  assert.deepEqual(result.label_vector, [1, 0, 0, 0, 0, 0, 0, 0, 0]);
});

test("Batch 32 haber işlenebilir", () => {
  const articles = Array.from({ length: 32 }, (_, index) => ({
    id: String(index),
    title: `OpenAI yapay zeka yazılım haberi ${index}`,
    summary: "Teknoloji ve API gelişmesi."
  }));
  const result = classifyArticlesLabels(articles);
  assert.equal(result.length, 32);
  assert.ok(result.every((article) => article.labels.includes("Teknoloji")));
});

test("/api/feed payloadına eklenecek alanlar oluşur", () => {
  const article = applyMultilabelToArticle({
    id: "feed-1",
    title: "Doktorlar yeni aşı araştırmasını duyurdu",
    summary: "Sağlık uzmanları ve bilim insanları tedavi çalışmasını yayımladı."
  });
  assert.ok(Array.isArray(article.labels));
  assert.ok(article.labels.includes("Sağlık"));
  assert.ok(article.labels.includes("Bilim"));
  assert.equal(article.num_labels, 9);
  assert.equal(article.label_vector.length, 9);
  assert.equal(typeof article.label_scores.Sağlık, "number");
});

test("Haber kartı rozetleri için kaynaklarda da etiket verisi oluşur", () => {
  const article = applyMultilabelToArticle({
    title: "NBA finalinde yıldız oyuncu maçın kaderini değiştirdi",
    summary: "Basketbol ve spor gündemi final sonrası hareketlendi.",
    sources: [{ sourceName: "Spor Kaynağı", title: "NBA final maçı" }]
  });
  assert.deepEqual(article.labels, ["Spor"]);
  assert.deepEqual(article.sources[0].labels, ["Spor"]);
});

test("E-gazete ve PDF için etiket grupları üretilebilir", () => {
  const articles = classifyArticlesLabels([
    { id: "1", title: "OpenAI yapay zeka API haberini duyurdu", summary: "Teknoloji ve yazılım gelişmesi." },
    { id: "2", title: "Borsa ve dolar yeni haftaya yükselişle başladı", summary: "Ekonomi piyasaları faiz kararını bekliyor." }
  ]);
  const groups = groupArticlesByLabel(articles);
  assert.equal(groups.Teknoloji.length, 1);
  assert.equal(groups.Ekonomi.length, 1);
  const stats = buildMultilabelStats(articles);
  assert.equal(stats.totalArticles, 2);
  assert.equal(stats.numLabels, 9);
});

test("İngilizce teknoloji ve ekonomi haberi doğru çoklu etiketlenir", () => {
  const result = classifyArticleLabels({
    title: "Central bank decision shakes technology stocks",
    summary: "OpenAI and chip companies led the market after a new artificial intelligence investment."
  });
  assert.ok(result.labels.includes("Teknoloji"));
  assert.ok(result.labels.includes("Ekonomi"));
  assert.ok(Object.values(result.label_scores).reduce((sum, value) => sum + value, 0) > 1);
});
