import { useState } from "react";
import { ftpFileUrl } from "../api.js";

export default function MailDetail({ email }) {
  const [bodyMode, setBodyMode] = useState(email.bodyHtml ? "html" : "text");

  return (
    <div className="detail" key={email.id}>
      <h2>{email.subject || "(no subject)"}</h2>
      <div className="meta">
        <div><b>From:</b> {email.fromAddress || "-"}</div>
        <div><b>To:</b> {email.toAddress || "-"}</div>
        {email.ccAddress && <div><b>Cc:</b> {email.ccAddress}</div>}
        {email.bccAddress && <div><b>Bcc:</b> {email.bccAddress}</div>}
        <div><b>Date:</b> {email.dateRaw || email.emailDate}</div>
        <div><b>Message-ID:</b> {email.messageId}</div>
      </div>

      <div className="body-toggle">
        <button
          className={bodyMode === "text" ? "btn primary" : "btn"}
          onClick={() => setBodyMode("text")}
          disabled={!email.bodyText}
        >
          Text
        </button>
        <button
          className={bodyMode === "html" ? "btn primary" : "btn"}
          onClick={() => setBodyMode("html")}
          disabled={!email.bodyHtml}
        >
          HTML
        </button>
      </div>

      <div className="body-frame">
        {bodyMode === "html" && email.bodyHtml ? (
          <iframe
            title="email-html-body"
            style={{ width: "100%", height: "360px", border: "none" }}
            srcDoc={email.bodyHtml}
          />
        ) : (
          <div>{email.bodyText || "(no plain-text body)"}</div>
        )}
      </div>

      {email.hasAttachments && (
        <div className="attachments">
          <h3 style={{ fontSize: 13, color: "var(--text-dim)" }}>
            Attachments ({email.attachmentCount})
          </h3>
          {email.attachments.map((a) => (
            <div className="attachment-row" key={`${a.category}-${a.index}`}>
              <span>
                <span className="badge">{a.category}</span> {a.filename}
              </span>
              <span className="attachment-actions">
                <a className="btn" href={ftpFileUrl(a.ftpPath, "inline")} target="_blank" rel="noreferrer">
                  View
                </a>
                <a className="btn" href={ftpFileUrl(a.ftpPath, "attachment")}>
                  Download
                </a>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
