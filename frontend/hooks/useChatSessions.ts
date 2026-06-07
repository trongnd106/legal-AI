"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ACTIVE_SESSION_KEY,
  CHAT_SESSIONS_KEY,
  DEFAULT_NEW_CHAT_TITLE,
  createNewSession,
  loadSessionsFromStorage,
  truncateTitle,
} from "@/lib/chatSessions";
import type { ChatMessage, ChatSession } from "@/types/api";

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const { sessions: stored, activeSessionId: activeId } =
      loadSessionsFromStorage();
    setSessions(stored);
    setActiveSessionId(activeId);
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(sessions));
    localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
  }, [sessions, activeSessionId, loaded]);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) ?? sessions[0] ?? null;

  const createNewChat = useCallback(() => {
    const session = createNewSession();
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
  }, []);

  const switchChat = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const updateSessionMessages = useCallback(
    (
      id: string,
      updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[]),
    ) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== id) return s;
          const messages =
            typeof updater === "function" ? updater(s.messages) : updater;
          return { ...s, messages, updatedAt: Date.now() };
        }),
      );
    },
    [],
  );

  const updateSessionTitle = useCallback((id: string, text: string) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== id || s.title !== DEFAULT_NEW_CHAT_TITLE) return s;
        return {
          ...s,
          title: truncateTitle(text),
          updatedAt: Date.now(),
        };
      }),
    );
  }, []);

  return {
    sessions,
    activeSessionId,
    activeSession,
    loaded,
    createNewChat,
    switchChat,
    updateSessionMessages,
    updateSessionTitle,
  };
}
