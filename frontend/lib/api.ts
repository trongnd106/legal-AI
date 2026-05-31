import type {
  ChatRequest,
  ChatResponse,
  DocumentItem,
  HealthResponse,
} from "@/types/api";

const API_BASE = "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = (await res.json()) as { detail?: string; message?: string };
      detail = err.detail || err.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listDocuments(): Promise<{ documents: DocumentItem[] }> {
  return request<{ documents: DocumentItem[] }>("/api/documents");
}

export async function previewDocument(
  docId: string,
): Promise<{ id: string; ten: string; content: string; truncated: boolean }> {
  return request(`/api/documents/${encodeURIComponent(docId)}/preview`);
}

export function downloadDocumentUrl(docId: string): string {
  return `${API_BASE}/api/documents/${encodeURIComponent(docId)}/download`;
}

export async function uploadDocument(
  file: File,
): Promise<{ message: string; filename: string; path: string }> {
  const form = new FormData();
  form.append("file", file);
  return request("/api/documents/upload", {
    method: "POST",
    body: form,
  });
}

export async function healthCheck(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function markdownLite(text: string): string {
  if (!text) return "";
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n- /g, "</p><ul><li>");
  html = html.replace(/\n(\d+)\. /g, "</p><ol><li>");
  if (!html.startsWith("<p>")) html = `<p>${html}</p>`;
  return html;
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return y && m && d ? `${d}/${m}/${y}` : iso;
}

export function fileTypeIcon(ext?: string): { emoji: string; cls: string } {
  const e = (ext || "txt").toLowerCase();
  if (e === "pdf") return { emoji: "📄", cls: "pdf" };
  if (e === "doc" || e === "docx") return { emoji: "📝", cls: "doc" };
  return { emoji: "📃", cls: "txt" };
}
