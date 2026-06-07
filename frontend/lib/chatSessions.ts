import type { ChatMessage, ChatSession } from "@/types/api";

export const CHAT_SESSIONS_KEY = "luat-lao-dong-chat-sessions";
export const ACTIVE_SESSION_KEY = "luat-lao-dong-active-session";
export const DEFAULT_NEW_CHAT_TITLE = "Cuộc trò chuyện mới";

export const WELCOME_HTML = `
  <p>Xin chào! Tôi là trợ lý tư vấn <strong>Luật Lao động Việt Nam</strong>.</p>
  <p>Tôi có thể hỗ trợ bạn tra cứu Bộ luật Lao động 2019 và các Nghị định hướng dẫn.</p>
  <ul>
    <li>Quyền và nghĩa vụ của người lao động</li>
    <li>Hợp đồng lao động, thử việc, chấm dứt HĐLĐ</li>
    <li>Lương, BHXH, thời giờ làm việc, nghỉ phép</li>
  </ul>
`;

export function createWelcomeMessages(): ChatMessage[] {
  return [
    {
      role: "bot",
      html: WELCOME_HTML,
      plain: "Xin chào!",
      timestamp: Date.now(),
    },
  ];
}

export function createNewSession(title = DEFAULT_NEW_CHAT_TITLE): ChatSession {
  const now = Date.now();
  return {
    id: String(now),
    title,
    messages: createWelcomeMessages(),
    createdAt: now,
    updatedAt: now,
  };
}

export function truncateTitle(text: string, maxLen = 28): string {
  return text.length > maxLen ? `${text.slice(0, maxLen)}...` : text;
}

export function loadSessionsFromStorage(): {
  sessions: ChatSession[];
  activeSessionId: string;
} {
  if (typeof window === "undefined") {
    const session = createNewSession();
    return { sessions: [session], activeSessionId: session.id };
  }

  try {
    const raw = localStorage.getItem(CHAT_SESSIONS_KEY);
    if (raw) {
      const sessions = JSON.parse(raw) as ChatSession[];
      if (sessions.length > 0) {
        const storedActive = localStorage.getItem(ACTIVE_SESSION_KEY);
        const activeSessionId =
          storedActive && sessions.some((s) => s.id === storedActive)
            ? storedActive
            : sessions[0].id;
        return { sessions, activeSessionId };
      }
    }
  } catch {
    // ignore corrupt storage
  }

  const session = createNewSession();
  return { sessions: [session], activeSessionId: session.id };
}
