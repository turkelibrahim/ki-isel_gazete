export function ArticlePreviewCard({ article }: { article: any }) {
  return <article className="admin-article-preview"><h3>{article.title}</h3><p>{article.summary}</p><small>{article.sourceName || article.source}</small></article>;
}
