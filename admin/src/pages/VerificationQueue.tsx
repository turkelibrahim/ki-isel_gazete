import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";

export function VerificationQueue() {
  const [queue, setQueue] = useState<any[]>([]);
  useEffect(() => { adminRequest("/api/admin/reclassify/queue?status=verification").then((data) => setQueue(data.queue || [])); }, []);
  return <main><h1>İkinci Admin Doğrulama</h1>{queue.map((item) => <button key={item.id} onClick={() => adminRequest(`/api/admin/verify/${item.id}`, { method: "POST", body: JSON.stringify({ approved: true }) })}>{item.article_id} onayla</button>)}</main>;
}
