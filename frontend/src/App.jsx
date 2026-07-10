import { useState } from "react";
import MailList from "./components/MailList.jsx";
import FileBrowser from "./components/FileBrowser.jsx";
import LogViewer from "./components/LogViewer.jsx";

const TABS = [
  { id: "mails", label: "Mails" },
  { id: "files", label: "Files" },
  { id: "logs", label: "Logs" },
];

export default function App() {
  const [tab, setTab] = useState("mails");

  return (
    <div className="app">
      <header className="app-header">
        <h1>TMS_ImportExport &mdash; Mail Ingestion Dashboard</h1>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {tab === "mails" && <MailList />}
        {tab === "files" && <FileBrowser />}
        {tab === "logs" && <LogViewer />}
      </main>
    </div>
  );
}
