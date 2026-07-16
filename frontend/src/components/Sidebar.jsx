import { useState } from "react";

const FOLDER_ICONS = ["📬", "📊", "📋", "🔧", "🏥", "🏦", "🛒", "📦", "💻", "📁"];

function folderIcon(name, index) {
  if (name === "Uncategorized") return "📥";
  return FOLDER_ICONS[index % FOLDER_ICONS.length];
}

export default function Sidebar({ folders, activeFolder, onSelect, loading }) {
  const [search, setSearch] = useState("");

  const filtered = (folders || []).filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-header">Companies / Folders</div>
      <input
        className="sidebar-search"
        type="text"
        placeholder="Search folders..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="folder-list">
        {loading && <div className="empty-state">Loading...</div>}
        {!loading && filtered.length === 0 && (
          <div className="empty-state">No folders found</div>
        )}
        {filtered.map((folder, i) => (
          <div
            key={folder.name}
            className={`folder-item${activeFolder === folder.name ? " active" : ""}`}
            onClick={() => onSelect(folder.name)}
          >
            <span className="folder-icon default">{folderIcon(folder.name, i)}</span>
            <span className="folder-name">{folder.name}</span>
            <span className="folder-count">{folder.count}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
