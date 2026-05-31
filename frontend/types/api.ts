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

export interface ChatMessage {
  role: "user" | "bot";
  html: string;
  plain?: string;
  citations?: string[];
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
}

export interface HealthResponse {
  status: string;
  graphrag_ready: boolean;
}
