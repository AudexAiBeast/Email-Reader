import { useEffect, useState } from "react";
import { graphqlQuery } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import MailList from "./components/MailList.jsx";
import LogViewer from "./components/LogViewer.jsx";
import FileBrowser from "./components/FileBrowser.jsx";

const FOLDERS_QUERY = `
  query Folders {
    folders {
      name
      count
    }
  }
`;

const TABS = [
  { id: "mails", label: "Mail" },
  { id: "files", label: "Files" },
  { id: "logs", label: "Logs" },
];

export default function App() {
  const [tab, setTab] = useState("mails");
  const [folders, setFolders] = useState([]);
  const [activeFolder, setActiveFolder] = useState(null);
  const [foldersLoading, setFoldersLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await graphqlQuery(FOLDERS_QUERY);
        setFolders(data.folders);
        if (data.folders.length > 0) {
          setActiveFolder(data.folders[0].name);
        }
      } catch {
        // silently fail
      } finally {
        setFoldersLoading(false);
      }
    }
    load();
  }, []);

  return (
    <>
      <header className="app-header">
        <div className="app-brand">
          <span className="logo-icon">AI</span>
          <div>
            <div>audAInsights</div>
            <div className="brand-sub">AI Mail Reader &amp; Organizer</div>
          </div>
        </div>
        <nav style={{ display: "flex", gap: 4 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "btn primary" : "btn"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="header-right">
          <span>🔮 Powered by Ollama</span>
        </div>
      </header>

      <div className="app-layout">
        {tab === "mails" && (
          <>
            <Sidebar
              folders={folders}
              activeFolder={activeFolder}
              onSelect={setActiveFolder}
              loading={foldersLoading}
            />
            <main className="main-content">
              <div className="main-toolbar">
                <span className="company-title">
                  {activeFolder || "All Mail"}
                </span>
              </div>
              <MailList companyName={activeFolder} />
            </main>
          </>
        )}
        {tab === "files" && (
          <main className="main-content" style={{ padding: "16px 20px", overflow: "auto" }}>
            <FileBrowser />
          </main>
        )}
        {tab === "logs" && (
          <main className="main-content" style={{ padding: "16px 20px", overflow: "auto" }}>
            <LogViewer />
          </main>
        )}
      </div>
    </>
  );
}
