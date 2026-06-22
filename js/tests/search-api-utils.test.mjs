import test from "node:test";
import assert from "node:assert/strict";
import { buildSearchParams } from "../utils/searchApi.js";

test("search params frontend ve backend ile uyumlu üretilir", () => {
  const params = buildSearchParams({ q: "ekonomi", category: "politika", source: "TRT Haber", sort: "most_read", page: 2, limit: 10 });
  assert.equal(params.get("q"), "ekonomi");
  assert.equal(params.get("category"), "politika");
  assert.equal(params.get("source"), "TRT Haber");
  assert.equal(params.get("sort"), "most_read");
  assert.equal(params.get("page"), "2");
  assert.equal(params.get("limit"), "10");
});
