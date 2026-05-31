import type { TabId } from "@/types/api";

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
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
    </aside>
  );
}
