import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";

export function FeedbackStats() {
  const [stats, setStats] = useState<any>();
  useEffect(() => { adminRequest("/api/admin/stats/feedback").then(setStats); }, []);
  return <main><h1>Feedback İstatistikleri</h1><pre>{JSON.stringify(stats, null, 2)}</pre></main>;
}
