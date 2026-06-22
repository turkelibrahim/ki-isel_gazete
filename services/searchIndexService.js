const SearchService = require("./searchService");

function buildLocalSearchDocument(article) {
  return SearchService.serializeArticle(SearchService.normalizeSearchArticleFields({ ...article }));
}

function rebuildLocalSearchIndex(db = {}) {
  SearchService.initSearchDb(db);
  return SearchService.getArticlePool(db).map(buildLocalSearchDocument);
}

module.exports = { buildLocalSearchDocument, rebuildLocalSearchIndex };
