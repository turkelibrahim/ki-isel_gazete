const SearchService = require("../services/searchService");

function queryToObject(url) {
  return Object.fromEntries(url.searchParams.entries());
}

async function handleSearchRoute(req, res, url, context = {}) {
  const { json, db, writeDb, getUserId = () => "anonymous" } = context;
  if (!url.pathname.startsWith("/api/search")) return false;
  SearchService.initSearchDb(db);

  if (req.method === "GET" && url.pathname === "/api/search") {
    const payload = SearchService.searchArticles(db, queryToObject(url), { userId: getUserId(req) });
    writeDb?.(db);
    return json(res, 200, payload);
  }

  if (req.method === "GET" && url.pathname === "/api/search/sources") {
    const data = SearchService.listSearchSources(db);
    return json(res, 200, { success: true, count: data.length, data });
  }

  if (req.method === "GET" && url.pathname === "/api/search/suggestions") {
    const q = url.searchParams.get("q") || "";
    const data = SearchService.buildSearchSuggestions(db, q, Number(url.searchParams.get("limit") || 8));
    return json(res, 200, { success: true, query: SearchService.sanitizeQuery(q), data });
  }

  return false;
}

module.exports = { handleSearchRoute };
