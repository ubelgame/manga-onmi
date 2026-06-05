const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function submitChapter(data: {
  source_url: string;
  series_name: string;
  chapter_number: string;
}) {
  const r = await fetch(`${API_BASE}/chapters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchChapters() {
  const r = await fetch(`${API_BASE}/chapters`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchPages(chapterId: string) {
  const r = await fetch(`${API_BASE}/chapters/${chapterId}/pages`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchPage(pageId: string) {
  const r = await fetch(`${API_BASE}/pages/${pageId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getImageUrl(pageId: string, stage: "raw" | "inpainted" | "final" = "final") {
  const r = await fetch(`${API_BASE}/pages/${pageId}/image-url?stage=${stage}`);
  if (!r.ok) return null;
  const data = await r.json();
  return data.url as string;
}

export async function overrideTranslation(blockId: string, englishText: string, tlNote?: string) {
  const r = await fetch(`${API_BASE}/blocks/${blockId}/translation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ english_text: englishText, tl_note: tlNote }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function reprocessPage(pageId: string) {
  const r = await fetch(`${API_BASE}/pages/${pageId}/reprocess`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchGlossary(chapterId: string) {
  const r = await fetch(`${API_BASE}/chapters/${chapterId}/glossary`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function addGlossaryTerm(chapterId: string, data: {
  japanese_term: string;
  english_term: string;
  term_type?: string;
}) {
  const r = await fetch(`${API_BASE}/chapters/${chapterId}/glossary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function uploadPageImage(pageId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${API_BASE}/pages/${pageId}/upload`, {
    method: "POST",
    body: form,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export function createPageWebSocket(pageId: string, onMessage: (data: any) => void) {
  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  const ws = new WebSocket(`${wsBase}/ws/pages/${pageId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
