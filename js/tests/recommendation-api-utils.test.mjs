import test from "node:test";
import assert from "node:assert/strict";
import { buildQuery } from "../utils/recommendationApi.js";

test("recommendation query builder skips empty values", () => {
  const query = buildQuery({ limit: 10, category: "Ekonomi", empty: "", nil: null });
  assert.equal(query.includes("limit=10"), true);
  assert.equal(query.includes("category=Ekonomi"), true);
  assert.equal(query.includes("empty"), false);
});
