import { useEffect, useState } from "react";
import { adminRequest } from "../services/adminApi";

export function RetrainingStatus() {
  const [status, setStatus] = useState<any>();
  useEffect(() => { adminRequest("/api/admin/retraining/status").then(setStatus); }, []);
  return <main><h1>Retraining Durumu</h1><pre>{JSON.stringify(status, null, 2)}</pre><button onClick={() => adminRequest("/api/admin/retraining/trigger", { method: "POST", body: JSON.stringify({ reason: "manual" }) })}>Manuel retraining tetikle</button></main>;
}
