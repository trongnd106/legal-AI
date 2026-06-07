"use client";

import { useEffect, useState } from "react";
import { useChatSessions } from "@/hooks/useChatSessions";
import { healthCheck } from "@/lib/api";
import type { TabId } from "@/types/api";
import { ChatPanel } from "./ChatPanel";
import { DocumentPanel } from "./DocumentPanel";
import { Sidebar } from "./Sidebar";
import { TabBar } from "./TabBar";
import { ToastProvider, useToast } from "./ToastProvider";

function AppContent() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const { showToast } = useToast();
  const {
    sessions,
    activeSessionId,
    activeSession,
    loaded,
    createNewChat,
    switchChat,
    updateSessionMessages,
    updateSessionTitle,
  } = useChatSessions();

  useEffect(() => {
    healthCheck()
      .then((health) => {
        if (!health.graphrag_ready) {
          showToast(
            "GraphRAG chưa sẵn sàng — chạy graphrag index trước. Chat có thể lỗi.",
            true,
          );
        }
      })
      .catch(() => {
        showToast("Không kết nối được API — chạy: python -m api.main", true);
      });
  }, [showToast]);

  const handleNewChat = () => {
    createNewChat();
    setActiveTab("chat");
  };

  const handleSwitchChat = (id: string) => {
    switchChat(id);
    setActiveTab("chat");
  };

  return (
    <div className="app-shell">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        chatSessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSwitchChat={handleSwitchChat}
      />
      <main className="main-content">
        <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <section
          id="tab-chat"
          className={`tab-content${activeTab === "chat" ? " active" : ""}`}
        >
          {loaded && activeSession && (
            <ChatPanel
              key={activeSession.id}
              sessionId={activeSession.id}
              messages={activeSession.messages}
              onMessagesChange={updateSessionMessages}
              onFirstUserMessage={updateSessionTitle}
            />
          )}
        </section>
        <section
          id="tab-panel"
          className={`tab-content${activeTab === "panel" ? " active" : ""}`}
        >
          <DocumentPanel />
        </section>
      </main>
    </div>
  );
}

export function AppShell() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
}
