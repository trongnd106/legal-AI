"use client";

import { useEffect, useState } from "react";
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

  return (
    <div className="app-shell">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="main-content">
        <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <section
          id="tab-chat"
          className={`tab-content${activeTab === "chat" ? " active" : ""}`}
        >
          <ChatPanel />
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
