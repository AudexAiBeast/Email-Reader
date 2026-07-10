import { useEffect, useRef, useState } from "react";

const MAX_LINES = 1000;

export default function LogViewer() {
  const [lines, setLines] = useState([]);
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const consoleRef = useRef(null);

  useEffect(() => {
    const source = new EventSource("/api/logs/stream");

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (event) => {
      const entry = JSON.parse(event.data);
      setLines((prev) => {
        const next = [...prev, entry];
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    };

    return () => source.close();
  }, []);

  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  return (
    <div>
      <div className="toolbar">
        <span>
          <span className={`status-dot ${connected ? "connected" : "disconnected"}`} />
          {connected ? "Live" : "Disconnected"}
        </span>
        <label>
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          Auto-scroll
        </label>
        <button className="btn" onClick={() => setLines([])}>
          Clear
        </button>
        <span className="badge">{lines.length} lines</span>
      </div>

      <div className="log-console" ref={consoleRef}>
        {lines.map((entry, i) => (
          <div className={`log-line level-${entry.level}`} key={i}>
            <span className="ts">{entry.timestamp.replace("T", " ").slice(0, 19)}</span>
            <span>[{entry.level}]</span> {entry.message}
          </div>
        ))}
        {!lines.length && <div className="empty-state">Waiting for log activity...</div>}
      </div>
    </div>
  );
}
