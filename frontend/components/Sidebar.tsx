import { MessageSquare, Plus } from "lucide-react";
import type { ChatSessionSummary, TabId } from "@/types/api";

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  chatSessions: ChatSessionSummary[];
  activeSessionId: string;
  onNewChat: () => void;
  onSwitchChat: (id: string) => void;
}

export function Sidebar({
  activeTab,
  onTabChange,
  chatSessions,
  activeSessionId,
  onNewChat,
  onSwitchChat,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-icon">⚖️</span>
        <span className="logo-text">Luật Lao Động AI</span>
      </div>
      <nav className="sidebar-nav">
        <button
          className={`nav-item${activeTab === "chat" ? " active" : ""}`}
          type="button"
          onClick={() => onTabChange("chat")}
        >
          <span className="nav-icon">💬</span>
          Hỏi đáp trực tuyến
        </button>
        <button
          className={`nav-item${activeTab === "panel" ? " active" : ""}`}
          type="button"
          onClick={() => onTabChange("panel")}
        >
          <span className="nav-icon">🗄️</span>
          Kho dữ liệu luật
        </button>
      </nav>

      <div className="history-section">
        <span className="history-label">Lịch sử trò chuyện</span>

        <button className="btn-new-chat" type="button" onClick={onNewChat}>
          <Plus size={16} aria-hidden />
          Cuộc trò chuyện mới
        </button>

        <ul className="history-list">
          {chatSessions.map((chat) => (
            <li key={chat.id}>
              <button
                className={`history-item${chat.id === activeSessionId ? " active" : ""}`}
                type="button"
                onClick={() => onSwitchChat(chat.id)}
              >
                <MessageSquare size={14} aria-hidden />
                <span className="history-title">{chat.title}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
