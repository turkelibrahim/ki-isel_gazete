import test from "node:test";
import assert from "node:assert/strict";

import {
  NAVBAR_CATEGORY_MAP,
  buildNavbarCategorySelection,
  filterArticlesByNavbarCategory,
  articleMatchesNavbarCategory
} from "../utils/categoryFilter.js";

test("Navbar kategori haritası backend etiketlerini değiştirmeden UI eşleşmesi yapar", () => {
  assert.equal(NAVBAR_CATEGORY_MAP.Politika.value, "Siyaset");
  assert.equal(NAVBAR_CATEGORY_MAP.Magazin.value, "Eğlence");
  assert.equal(NAVBAR_CATEGORY_MAP.Gündem.type, "special");
  assert.equal(NAVBAR_CATEGORY_MAP.Gündem.filter, "trending_or_latest");
});

test("Politika seçimi labels içinde Siyaset arar", () => {
  const selected = buildNavbarCategorySelection("Politika");
  const result = filterArticlesByNavbarCategory([
    { id: "1", title: "Meclis görüşmesi", labels: ["Siyaset"] },
    { id: "2", title: "Konser haberi", labels: ["Eğlence"] }
  ], selected);
  assert.deepEqual(result.map((article) => article.id), ["1"]);
});

test("Magazin seçimi labels yoksa category alanında Eğlence arar", () => {
  const selected = buildNavbarCategorySelection("Magazin");
  const result = filterArticlesByNavbarCategory([
    { id: "1", category: "Eğlence" },
    { id: "2", category: "Spor" }
  ], selected);
  assert.deepEqual(result.map((article) => article.id), ["1"]);
});

test("Gündem özel filtresi trend, önem veya çok kaynaklı haberleri en yeni sıralar", () => {
  const selected = buildNavbarCategorySelection("Gündem");
  const result = filterArticlesByNavbarCategory([
    { id: "old", publishedAt: "2026-06-20T09:00:00Z", source_count: 1 },
    { id: "multi", publishedAt: "2026-06-21T09:00:00Z", source_count: 4 },
    { id: "important", publishedAt: "2026-06-22T09:00:00Z", importance_score: 0.9 },
    { id: "trend", publishedAt: "2026-06-19T09:00:00Z", is_trending: true }
  ], selected);
  assert.deepEqual(result.map((article) => article.id), ["important", "multi", "trend"]);
});

test("Gündem metrik yoksa patlamaz ve haberleri en yeni sıralar", () => {
  const selected = buildNavbarCategorySelection("Gündem");
  const result = filterArticlesByNavbarCategory([
    { id: "a", publishedAt: "2026-06-20T09:00:00Z" },
    { id: "b", publishedAt: "2026-06-22T09:00:00Z" }
  ], selected);
  assert.deepEqual(result.map((article) => article.id), ["b", "a"]);
});

test("İzinsiz etiketler filtre eşleşmesi üretmez", () => {
  const selected = buildNavbarCategorySelection("Teknoloji");
  assert.equal(articleMatchesNavbarCategory({ labels: ["Gündem", "Genel"] }, selected), false);
});
