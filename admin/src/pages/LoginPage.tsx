import { useState } from "react";

export function LoginPage() {
  const [username, setUsername] = useState("superadmin");
  const [password, setPassword] = useState("");
  async function submit() {
    const response = await fetch("/api/admin/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
    const data = await response.json();
    if (data.token) localStorage.setItem("smart_admin_token", data.token);
  }
  return <main><h1>Admin Girişi</h1><input value={username} onChange={(e) => setUsername(e.target.value)} /><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /><button onClick={submit}>Giriş yap</button></main>;
}
