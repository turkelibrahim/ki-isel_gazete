const NewsProcessingService = require("../services/newsProcessingService");

async function handleNlpRoute(req, res, url, { readBody, json }) {
  if (req.method === "GET" && url.pathname === "/api/nlp/health") {
    return json(res, 200, { success: true, ...NewsProcessingService.health() });
  }

  if (req.method === "POST" && url.pathname === "/api/nlp/process") {
    const body = await readBody(req);
    const article = body.article || body;
    const processed = NewsProcessingService.processArticle(article);
    const enriched = NewsProcessingService.enrichFeedArticle(article);
    return json(res, 200, { success: true, processed, article: enriched });
  }

  if (req.method === "POST" && url.pathname === "/api/nlp/process-batch") {
    const body = await readBody(req);
    const articles = Array.isArray(body.articles) ? body.articles : [];
    const processed = NewsProcessingService.processBatch(articles);
    const enriched = articles.map((article) => NewsProcessingService.enrichFeedArticle(article));
    return json(res, 200, {
      success: true,
      count: processed.length,
      processed,
      articles: enriched
    });
  }

  return false;
}

module.exports = {
  prefix: "/api/nlp",
  endpoints: ["GET /api/nlp/health", "POST /api/nlp/process", "POST /api/nlp/process-batch"],
  handleNlpRoute
};
