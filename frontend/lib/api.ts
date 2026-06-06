import type {
  ChatRequest,
  ChatResponse,
  DocumentItem,
  HealthResponse,
} from "@/types/api";

const API_BASE = "";

const DEFAULT_TIMEOUT_MS = 15_000;
const CHAT_TIMEOUT_MS = 160_000;

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json", ...options.headers },
      signal: controller.signal,
      ...options,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(
        `Yêu cầu quá thời gian chờ (${Math.round(timeoutMs / 1000)}s). Vui lòng thử lại.`,
      );
    }
    // Lỗi mạng / kết nối bị ngắt (ECONNRESET, Failed to fetch, v.v.)
    const msg = err instanceof Error ? err.message : String(err);
    if (
      msg.includes("Failed to fetch") ||
      msg.includes("NetworkError") ||
      msg.includes("ECONNRESET") ||
      msg.includes("socket hang up")
    ) {
      throw new Error(
        "Kết nối đến server bị gián đoạn. Server có thể đang xử lý câu hỏi — vui lòng thử lại.",
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json() as { detail?: unknown; message?: unknown };
      const raw = body.detail ?? body.message;
      if (typeof raw === "string" && raw.length > 0) {
        detail = raw;
      } else if (raw != null) {
        detail = JSON.stringify(raw);
      }
    } catch {
      // Body không phải JSON (ví dụ: HTML error page từ proxy)
      if (res.status === 503) {
        detail = "Model AI đang quá tải, vui lòng thử lại sau ít phút.";
      } else if (res.status === 504) {
        detail = "Server mất quá nhiều thời gian xử lý, vui lòng thử lại.";
      } else if (res.status >= 500) {
        detail = "Lỗi server nội bộ. Vui lòng thử lại hoặc liên hệ quản trị viên.";
      }
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

export async function sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>(
    "/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    CHAT_TIMEOUT_MS,
  );
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
