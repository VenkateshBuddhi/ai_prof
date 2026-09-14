import axios from "axios";

// Backend base URL. Set NEXT_PUBLIC_API_URL in .env.local; falls back to local dev.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 8000,
});

// Dev-bypass auth scope (until real auth). The backend reads X-Role / X-* headers.
// Swap this for a real token/role once Supabase-JWT auth is wired.
api.defaults.headers.common["X-Role"] = "platform_admin";

export async function apiGet<T>(url: string): Promise<T> {
  const res = await api.get<T>(url);
  return res.data;
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.post<T>(url, body ?? {});
  return res.data;
}
