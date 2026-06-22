const SearchService = require("../services/searchService");

async function handleTrendsRoute(req, res, url, context = {}) {
  const { json, db, writeDb } = context;
  if (req.method === "GET" && url.pathname === "/api/trends") {
    SearchService.initSearchDb(db);
    const payload = SearchService.getTrends(db, Object.fromEntries(url.searchParams.entries()));
    writeDb?.(db);
    return json(res, 200, payload);
  }
  return false;
}

module.exports = { handleTrendsRoute };
