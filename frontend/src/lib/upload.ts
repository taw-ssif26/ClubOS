import { api } from "./api";
export async function uploadImage(slug: string, file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const r = await api<{ url: string }>(`/clubs/${slug}/uploads`, { method: "POST", form });
  return r.url;
}
