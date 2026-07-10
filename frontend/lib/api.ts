import type {
  ChatRequest,
  ChatResponse,
  ChatSession,
  ChatSessionListResponse,
  ContractAnalysisResponse,
  CreateSessionRequest,
  DocumentItem,
  HealthResponse,
  UpdateSessionRequest,
} from "@/types/api";

const API_BASE = "";

const DEFAULT_TIMEOUT_MS = 15_000;
const CHAT_TIMEOUT_MS = 160_000;

// Lỗi mạng tạm thời — đáng retry (không phải lỗi logic từ server)
const RETRYABLE_MESSAGES = [
  "Failed to fetch",
  "NetworkError",
  "ECONNRESET",
  "socket hang up",
  "Load failed",          // Safari
  "network error",
];

function isRetryableNetworkError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return RETRYABLE_MESSAGES.some((s) => msg.toLowerCase().includes(s.toLowerCase()));
}

function isRetryableStatus(status: number): boolean {
  // 503 = server overload / unavailable, 502/504 = proxy/gateway timeout
  return status === 502 || status === 503 || status === 504;
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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
      if (res.status === 503) {
        detail = "Model AI đang quá tải, vui lòng thử lại sau ít phút.";
      } else if (res.status === 504) {
        detail = "Server mất quá nhiều thời gian xử lý, vui lòng thử lại.";
      } else if (res.status >= 500) {
        detail = "Lỗi server nội bộ. Vui lòng thử lại hoặc liên hệ quản trị viên.";
      }
    }
    const error = new Error(detail) as Error & { status?: number };
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

export type RetryOptions = {
  /** Số lần thử tối đa (lần đầu + số lần retry). Mặc định 3. */
  maxAttempts?: number;
  /** Delay ban đầu (ms) trước retry 1. Tăng gấp đôi mỗi lần. Mặc định 1000ms. */
  baseDelayMs?: number;
  /** Callback được gọi mỗi lần chuẩn bị retry, với lần thử tiếp theo và delay (ms). */
  onRetry?: (attempt: number, delayMs: number, reason: string) => void;
};

/**
 * Bọc request() với auto-retry cho lỗi mạng tạm thời (ECONNRESET, 502/503/504).
 * Lỗi logic (400, 401, 404, 422) không được retry vì server trả lời hợp lệ.
 */
async function requestWithRetry<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
  retryOpts: RetryOptions = {},
): Promise<T> {
  const { maxAttempts = 3, baseDelayMs = 1_000, onRetry } = retryOpts;

  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await request<T>(path, options, timeoutMs);
    } catch (err) {
      lastError = err;

      const status = (err as { status?: number }).status;
      const retryable = isRetryableNetworkError(err) || (status !== undefined && isRetryableStatus(status));

      // Không retry nếu: lỗi logic, lần thử cuối, hoặc user đã abort
      if (!retryable || attempt === maxAttempts) break;
      if (err instanceof DOMException && err.name === "AbortError") break;

      const delayMs = baseDelayMs * 2 ** (attempt - 1); // 1s, 2s, 4s...
      const reason = isRetryableNetworkError(err)
        ? "kết nối bị ngắt"
        : `lỗi server ${status}`;

      onRetry?.(attempt + 1, delayMs, reason);
      await sleep(delayMs);
    }
  }

  throw lastError;
}

export async function sendChatMessage(
  payload: ChatRequest,
  retryOpts?: RetryOptions,
): Promise<ChatResponse> {
  return requestWithRetry<ChatResponse>(
    "/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    CHAT_TIMEOUT_MS,
    retryOpts,
  );
}

export async function streamChatMessage(
  payload: ChatRequest,
  callbacks: {
    onToken: (token: string) => void;
    onDone: (result: ChatResponse) => void;
    onError: (error: string) => void;
  },
  retryOpts?: RetryOptions,
): Promise<void> {
  const { maxAttempts = 3, baseDelayMs = 1_000 } = retryOpts ?? {};

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let detail = res.statusText;
        try {
          const body = await res.json() as { detail?: unknown };
          if (typeof body.detail === "string") detail = body.detail;
        } catch { /* ignore */ }
        throw Object.assign(new Error(detail), { status: res.status });
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("Response body is null");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let data: Record<string, unknown>;
          try {
            data = JSON.parse(raw);
          } catch { continue; }

          switch (data.type) {
            case "token":
              callbacks.onToken(String(data.content ?? ""));
              break;
            case "done":
              callbacks.onDone(data as unknown as ChatResponse);
              return;
            case "error":
              callbacks.onError(String(data.message ?? "Lỗi không xác định"));
              return;
          }
        }
      }
      return;
    } catch (err) {
      const status = (err as { status?: number }).status;
      const retryable = isRetryableNetworkError(err) || (status !== undefined && isRetryableStatus(status));
      if (!retryable || attempt === maxAttempts) {
        callbacks.onError(err instanceof Error ? err.message : "Lỗi không xác định");
        return;
      }
      const delayMs = baseDelayMs * 2 ** (attempt - 1);
      await sleep(delayMs);
    }
  }
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

export async function analyzeContract(
  file: File,
  wageRegion: string = "IV",
  skipLlmReview: boolean = false,
  retryOpts?: RetryOptions,
): Promise<ContractAnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("wage_region", wageRegion);
  form.append("skip_llm_review", String(skipLlmReview));
  return requestWithRetry<ContractAnalysisResponse>(
    "/api/contract/analyze",
    { method: "POST", body: form },
    300_000,
    { maxAttempts: 2, baseDelayMs: 2_000, ...retryOpts },
  );
}

export interface ContractProgressEvent {
  type: "progress";
  message: string;
}

export interface ContractDoneEvent extends ContractAnalysisResponse {
  type: "done";
}

export type ContractStreamEvent = ContractProgressEvent | ContractDoneEvent | { type: "error"; message: string };

export async function streamContractAnalysis(
  file: File,
  wageRegion: string = "IV",
  skipLlmReview: boolean = false,
  callbacks: {
    onProgress: (message: string) => void;
    onDone: (result: ContractAnalysisResponse) => void;
    onError: (error: string) => void;
  },
): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  form.append("wage_region", wageRegion);
  form.append("skip_llm_review", String(skipLlmReview));

  try {
    const res = await fetch("/api/contract/analyze/stream", {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json() as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
      } catch { /* ignore */ }
      callbacks.onError(detail);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      callbacks.onError("Response body is null");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let data: Record<string, unknown>;
        try {
          data = JSON.parse(raw);
        } catch { continue; }

        switch (data.type) {
          case "progress":
            callbacks.onProgress(String(data.message ?? ""));
            break;
          case "done":
            callbacks.onDone(data as unknown as ContractAnalysisResponse);
            return;
          case "error":
            callbacks.onError(String(data.message ?? "Lỗi không xác định"));
            return;
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err.message : "Lỗi không xác định");
  }
}

export async function healthCheck(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function fetchChatSessionList(): Promise<ChatSessionListResponse> {
  return request<ChatSessionListResponse>("/api/chat-sessions");
}

export async function fetchChatSession(sessionId: string): Promise<ChatSession> {
  return request<ChatSession>(
    `/api/chat-sessions/${encodeURIComponent(sessionId)}`,
  );
}

export async function createChatSession(
  payload: CreateSessionRequest = {},
): Promise<ChatSession> {
  return request<ChatSession>("/api/chat-sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateChatSession(
  sessionId: string,
  payload: UpdateSessionRequest,
): Promise<ChatSession> {
  return request<ChatSession>(
    `/api/chat-sessions/${encodeURIComponent(sessionId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteChatSession(
  sessionId: string,
): Promise<void> {
  return request<void>(
    `/api/chat-sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
}

export async function setActiveChatSession(
  activeSessionId: string,
): Promise<ChatSessionListResponse> {
  return request<ChatSessionListResponse>("/api/chat-sessions/active", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ activeSessionId }),
  });
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
