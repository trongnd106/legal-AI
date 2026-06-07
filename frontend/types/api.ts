export type TabId = "chat" | "panel";

export interface DocumentItem {
  id: string;
  ten: string;
  so_hieu: string;
  loai: string;
  tinh_trang: string;
  ngay_hieu_luc?: string | null;
  ngay_ban_hanh?: string | null;
  size_bytes: number;
  extension: string;
  updated_at?: string | null;
  source: "indexed" | "upload";
}

export interface DataCitationItem {
  key: string;
  type: string;
  id: string;
  label: string;
  detail: string;
  icon?: string;
  type_label?: string;
}

export interface ChatMessage {
  role: "user" | "bot";
  html?: string;
  markdown?: string;
  plain?: string;
  citations?: string[];
  dataCitations?: DataCitationItem[];
  timestamp?: number;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

export interface ChatSession extends ChatSessionSummary {
  messages: ChatMessage[];
}

export interface ChatRequest {
  question: string;
  mode?: "local" | "global";
  domain?: string;
}

export interface ChatResponse {
  answer: string;
  mode: string;
  article_citations: string[];
  entities_used?: string[];
  temporal_warnings?: string[];
  data_citations?: DataCitationItem[];
}

export interface HealthResponse {
  status: string;
  graphrag_ready: boolean;
}

export interface ChatSessionListResponse {
  sessions: ChatSessionSummary[];
  activeSessionId: string;
  storagePath: string;
}

export interface CreateSessionRequest {
  id?: string;
  title?: string;
  messages?: ChatMessage[];
}

export interface UpdateSessionRequest {
  title?: string;
  messages?: ChatMessage[];
}
