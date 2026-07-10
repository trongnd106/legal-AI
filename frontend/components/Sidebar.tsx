import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { ChatSessionSummary, TabId } from "@/types/api";

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  chatSessions: ChatSessionSummary[];
  activeSessionId: string;
  onNewChat: () => void;
  onSwitchChat: (id: string) => void;
  onDeleteChat: (id: string) => void;
}

export function Sidebar({
  activeTab,
  onTabChange,
  chatSessions,
  activeSessionId,
  onNewChat,
  onSwitchChat,
  onDeleteChat,
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
            <li key={chat.id} className="history-list-item">
              <button
                className={`history-item${chat.id === activeSessionId ? " active" : ""}`}
                type="button"
                onClick={() => onSwitchChat(chat.id)}
              >
                <MessageSquare size={14} aria-hidden />
                <span className="history-title">{chat.title}</span>
              </button>
              <button
                className="btn-delete-chat"
                type="button"
                title="Xóa cuộc trò chuyện"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm("Bạn có chắc muốn xóa cuộc trò chuyện này?")) {
                    onDeleteChat(chat.id);
                  }
                }}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
