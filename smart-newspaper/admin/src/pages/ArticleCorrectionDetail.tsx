import { useState } from "react";
import { adminRequest } from "../services/adminApi";
import { CategorySelector } from "../components/CategorySelector";
import { CorrectionReasonBox } from "../components/CorrectionReasonBox";

export function ArticleCorrectionDetail({ article }: { article: any }) {
  const [labels, setLabels] = useState<string[]>(article.labels || []);
  const [reason, setReason] = useState("");
  async function save() { await adminRequest("/api/admin/reclassify", { method: "POST", body: JSON.stringify({ article_id: article.id, corrected_labels: labels, correction_reason: reason }) }); }
  return <main><h1>Haber Düzelt</h1><h2>{article.title}</h2><CategorySelector value={labels} onChange={setLabels} /><CorrectionReasonBox value={reason} onChange={setReason} /><button onClick={save}>Kaydet</button></main>;
}
