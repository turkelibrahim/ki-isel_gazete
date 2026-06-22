import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";

export function ReclassificationQueue() {
  const [queue, setQueue] = useState<any[]>([]);
  useEffect(() => { adminRequest("/api/admin/reclassify/queue").then((data) => setQueue(data.queue || [])); }, []);
  return <main><h1>Yanlış Sınıflandırma Kuyruğu</h1>{queue.map((item) => <article key={item.id}>{item.article_id} - {item.feedback_status}</article>)}</main>;
}
