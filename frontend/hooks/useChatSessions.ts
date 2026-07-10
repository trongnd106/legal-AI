"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createChatSession,
  deleteChatSession,
  fetchChatSession,
  fetchChatSessionList,
  setActiveChatSession,
  updateChatSession,
} from "@/lib/api";
import {
  clearLegacyLocalStorage,
  createNewSession,
  DEFAULT_NEW_CHAT_TITLE,
  loadLegacySessionsFromLocalStorage,
  truncateTitle,
} from "@/lib/chatSessions";
import type { ChatMessage, ChatSessionSummary } from "@/types/api";
import { useToast } from "@/components/ToastProvider";

const PERSIST_DEBOUNCE_MS = 400;

async function migrateLegacySessions(): Promise<boolean> {
  const legacy = loadLegacySessionsFromLocalStorage();
  const hasLegacyData =
    legacy.sessions.length > 1 ||
    legacy.sessions[0]?.messages.some((m) => m.role === "user");

  if (!hasLegacyData) return false;

  for (const session of legacy.sessions) {
    await createChatSession({
      id: session.id,
      title: session.title,
      messages: session.messages,
    });
  }

  if (legacy.activeSessionId) {
    await setActiveChatSession(legacy.activeSessionId);
  }

  clearLegacyLocalStorage();
  return true;
}

export function useChatSessions() {
  const { showToast } = useToast();
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [storagePath, setStoragePath] = useState<string>("");

  const messagesCacheRef = useRef<Map<string, ChatMessage[]>>(new Map());
  const skipPersistRef = useRef(true);
  const pendingTitleRef = useRef<string | null>(null);

  const loadSessionContent = useCallback(
    async (sessionId: string, useCache = true) => {
      if (useCache) {
        const cached = messagesCacheRef.current.get(sessionId);
        if (cached) {
          setActiveMessages(cached);
          return;
        }
      }

      setSessionLoading(true);
      try {
        const session = await fetchChatSession(sessionId);
        messagesCacheRef.current.set(sessionId, session.messages);
        setActiveMessages(session.messages);
      } catch {
        showToast("Không tải được nội dung cuộc trò chuyện", true);
      } finally {
        setSessionLoading(false);
      }
    },
    [showToast],
  );

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        let list = await fetchChatSessionList();
        if (cancelled) return;

        if (list.sessions.length === 0) {
          const migrated = await migrateLegacySessions();
          if (migrated) {
            list = await fetchChatSessionList();
            if (cancelled) return;
            showToast("Đã chuyển lịch sử chat sang thư mục .legalai trên máy");
          } else {
            await createChatSession();
            list = await fetchChatSessionList();
            if (cancelled) return;
          }
        }

        setSessions(list.sessions);
        setStoragePath(list.storagePath);

        const activeId =
          list.activeSessionId || list.sessions[0]?.id || "";
        setActiveSessionId(activeId);

        if (activeId) {
          await loadSessionContent(activeId, false);
        }
      } catch {
        if (cancelled) return;
        const legacy = loadLegacySessionsFromLocalStorage();
        setSessions(
          legacy.sessions.map(({ id, title, createdAt, updatedAt }) => ({
            id,
            title,
            createdAt,
            updatedAt,
          })),
        );
        setActiveSessionId(legacy.activeSessionId);
        setActiveMessages(
          legacy.sessions.find((s) => s.id === legacy.activeSessionId)
            ?.messages ?? legacy.sessions[0]?.messages ?? [],
        );
        showToast(
          "Không kết nối được server — lịch sử chỉ lưu tạm trong phiên này",
          true,
        );
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }

    void init();
    return () => {
      cancelled = true;
    };
  }, [loadSessionContent, showToast]);

  useEffect(() => {
    if (!loaded || !activeSessionId) return;

    if (skipPersistRef.current) {
      skipPersistRef.current = false;
      return;
    }

    const timer = setTimeout(() => {
      const payload: { messages: ChatMessage[]; title?: string } = {
        messages: activeMessages,
      };
      if (pendingTitleRef.current) {
        payload.title = pendingTitleRef.current;
        pendingTitleRef.current = null;
      }

      void updateChatSession(activeSessionId, payload)
        .then((session) => {
          messagesCacheRef.current.set(session.id, session.messages);
          setSessions((prev) =>
            prev.map((s) =>
              s.id === session.id
                ? {
                    id: session.id,
                    title: session.title,
                    createdAt: session.createdAt,
                    updatedAt: session.updatedAt,
                  }
                : s,
            ),
          );
          setStoragePath((prev) => prev);
        })
        .catch(() => {
          showToast("Không lưu được lịch sử cuộc trò chuyện", true);
        });
    }, PERSIST_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [activeMessages, activeSessionId, loaded, showToast]);

  const createNewChat = useCallback(async () => {
    try {
      const session = await createChatSession();
      const summary: ChatSessionSummary = {
        id: session.id,
        title: session.title,
        createdAt: session.createdAt,
        updatedAt: session.updatedAt,
      };
      messagesCacheRef.current.set(session.id, session.messages);
      setSessions((prev) => [summary, ...prev]);
      setActiveSessionId(session.id);
      setActiveMessages(session.messages);
      skipPersistRef.current = true;
    } catch {
      const fallback = createNewSession();
      const summary: ChatSessionSummary = {
        id: fallback.id,
        title: fallback.title,
        createdAt: fallback.createdAt,
        updatedAt: fallback.updatedAt,
      };
      messagesCacheRef.current.set(fallback.id, fallback.messages);
      setSessions((prev) => [summary, ...prev]);
      setActiveSessionId(fallback.id);
      setActiveMessages(fallback.messages);
      showToast("Không tạo được cuộc trò chuyện mới trên server", true);
    }
  }, [showToast]);

  const switchChat = useCallback(
    async (id: string) => {
      if (id === activeSessionId) return;

      setActiveSessionId(id);
      void setActiveChatSession(id).catch(() => {
        showToast("Không cập nhật được cuộc trò chuyện đang mở", true);
      });
      await loadSessionContent(id);
    },
    [activeSessionId, loadSessionContent, showToast],
  );

  const deleteChat = useCallback(
    async (id: string) => {
      try {
        await deleteChatSession(id);
        messagesCacheRef.current.delete(id);

        let nextActiveId: string | null = null;
        setSessions((prev) => {
          const filtered = prev.filter((s) => s.id !== id);
          if (id === activeSessionId) {
            nextActiveId = filtered.length > 0 ? filtered[0].id : null;
          }
          return filtered;
        });

        if (id === activeSessionId) {
          if (nextActiveId) {
            setActiveSessionId(nextActiveId);
            void loadSessionContent(nextActiveId);
          } else {
            void createNewChat();
          }
        }

        showToast("Đã xóa cuộc trò chuyện");
      } catch {
        showToast("Không xóa được cuộc trò chuyện", true);
      }
    },
    [activeSessionId, loadSessionContent, createNewChat, showToast],
  );

  const updateSessionMessages = useCallback(
    (
      id: string,
      updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
    ) => {
      setActiveMessages((prev) => {
        const next =
          typeof updater === "function" ? updater(prev) : updater;
        messagesCacheRef.current.set(id, next);
        return next;
      });
    },
    [],
  );

  const updateSessionTitle = useCallback((id: string, text: string) => {
    const title = truncateTitle(text);
    pendingTitleRef.current = title;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== id || s.title !== DEFAULT_NEW_CHAT_TITLE) return s;
        return { ...s, title, updatedAt: Date.now() };
      }),
    );
  }, []);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) ?? sessions[0] ?? null;

  return {
    sessions,
    activeSessionId,
    activeSession,
    activeMessages,
    sessionLoading,
    loaded,
    storagePath,
    createNewChat,
    deleteChat,
    switchChat,
    updateSessionMessages,
    updateSessionTitle,
  };
}
