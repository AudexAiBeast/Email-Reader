import { useEffect, useState } from "react";
import { listFtpDir, ftpFileUrl } from "../api.js";

function formatSize(bytes) {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function FileBrowser() {
  const [path, setPath] = useState("/");
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listFtpDir(path)
      .then((data) => {
        if (!cancelled) setEntries(data.entries);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  const segments = path.split("/").filter(Boolean);

  function goTo(index) {
    const next = "/" + segments.slice(0, index + 1).join("/");
    setPath(index < 0 ? "/" : next);
  }

  function openDir(name) {
    const next = path.endsWith("/") ? `${path}${name}` : `${path}/${name}`;
    setPath(next);
  }

  return (
    <div>
      <div className="breadcrumbs">
        <button onClick={() => goTo(-1)}>root</button>
        {segments.map((seg, i) => (
          <span key={i}>
            <span>/</span>
            <button onClick={() => goTo(i)}>{seg}</button>
          </span>
        ))}
      </div>

      {error && <div className="empty-state">Error: {error}</div>}
      {loading && <div className="empty-state">Loading...</div>}

      {!loading && !error && (
        <div className="panel">
          {entries.map((entry) => {
            const filePath = path.endsWith("/") ? `${path}${entry.name}` : `${path}/${entry.name}`;
            return (
              <div className="file-row" key={entry.name}>
                <span
                  className={entry.is_dir ? "file-name dir" : "file-name"}
                  onClick={() => entry.is_dir && openDir(entry.name)}
                >
                  {entry.is_dir ? "📁" : "📄"} {entry.name}
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {!entry.is_dir && <span className="badge">{formatSize(entry.size)}</span>}
                  {!entry.is_dir && (
                    <span className="attachment-actions">
                      <a className="btn" href={ftpFileUrl(filePath, "inline")} target="_blank" rel="noreferrer">
                        View
                      </a>
                      <a className="btn" href={ftpFileUrl(filePath, "attachment")}>
                        Download
                      </a>
                    </span>
                  )}
                </span>
              </div>
            );
          })}
          {!entries.length && <div className="empty-state">This folder is empty.</div>}
        </div>
      )}
    </div>
  );
}
