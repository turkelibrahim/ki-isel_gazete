export const ALLOWED_CATEGORIES = ["Teknoloji", "Siyaset", "Spor", "Ekonomi", "Eğlence", "Sağlık", "Bilim", "Dünya", "Yaşam"] as const;

export async function adminRequest(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("smart_admin_token") || "";
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  const data = await response.json();
  if (!response.ok || data.success === false) throw new Error(data?.error?.message || "Admin API hatası");
  return data;
}
