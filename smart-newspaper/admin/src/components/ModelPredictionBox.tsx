export function ModelPredictionBox({ article }: { article: any }) {
  return <section className="admin-model-box"><strong>Model tahmini</strong><p>Kategori: {article.category}</p><p>Etiketler: {(article.labels || []).join(", ")}</p><p>LLM: {article.llm_validation?.provider || "-"}</p></section>;
}
