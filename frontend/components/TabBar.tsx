import type { TabId } from "@/types/api";

interface TabBarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export function TabBar({ activeTab, onTabChange }: TabBarProps) {
  return (
    <div className="tab-bar">
      <button
        className={`tab${activeTab === "chat" ? " active" : ""}`}
        type="button"
        data-tab="chat"
        onClick={() => onTabChange("chat")}
      >
        chat
      </button>
      <button
        className={`tab${activeTab === "panel" ? " active" : ""}`}
        type="button"
        data-tab="panel"
        onClick={() => onTabChange("panel")}
      >
        panel
      </button>
    </div>
  );
}
