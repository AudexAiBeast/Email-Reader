import { useState } from "react";
import { ftpFileUrl } from "../api.js";
import AiSummary from "./AiSummary.jsx";

export default function MailDetail({ email }) {
  const [bodyMode, setBodyMode] = useState(email.bodyHtml ? "html" : "text");

  if (!email) {
    return <div className="empty-state">Select an email to view its content.</div>;
  }

  return (
    <div className="detail-scroll" key={email.id}>
      <div className="detail-header">
        <h2>{email.subject || "(no subject)"}</h2>
      </div>

      <div className="detail-meta">
        <div>
          <span className="meta-label">From:</span>
          <span className="meta-value">{email.fromAddress || "-"}</span>
          <span className="company-tag">
            {email.companyName || "Uncategorized"}
          </span>
        </div>
        <div>
          <span className="meta-label">To:</span>
          <span className="meta-value">{email.toAddress || "-"}</span>
        </div>
        {email.ccAddress && (
          <div>
            <span className="meta-label">Cc:</span>
            <span className="meta-value">{email.ccAddress}</span>
          </div>
        )}
        <div>
          <span className="meta-label">Date:</span>
          <span className="meta-value">{email.dateRaw || email.emailDate}</span>
        </div>
        {email.companyDomainSource && (
          <div>
            <span className="meta-label">Domain:</span>
            <span className="meta-value">{email.companyDomainSource}</span>
          </div>
        )}
        {email.companySignatureSource && (
          <div>
            <span className="meta-label">Signature:</span>
            <span className="meta-value">{email.companySignatureSource}</span>
          </div>
        )}
      </div>

      <AiSummary emailId={email.id} existingSummary={email.aiSummary} companyName={email.companyName} />

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

      <div className="body-content">
        {bodyMode === "html" && email.bodyHtml ? (
          <iframe
            title="email-html-body"
            srcDoc={email.bodyHtml}
          />
        ) : (
          <div>{email.bodyText || "(no plain-text body)"}</div>
        )}
      </div>

      {email.hasAttachments && (
        <div className="attachments-section">
          <h3>Attachments ({email.attachmentCount})</h3>
          {email.attachments.map((a) => (
            <div className="attachment-row" key={`${a.category}-${a.index}`}>
              <div className="att-info">
                <span className="badge">{a.category}</span>
                <span className="att-name">{a.filename}</span>
              </div>
              <div className="attachment-actions">
                <a className="btn" href={ftpFileUrl(a.ftpPath, "inline")} target="_blank" rel="noreferrer">
                  View
                </a>
                <a className="btn" href={ftpFileUrl(a.ftpPath, "attachment")}>
                  Download
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {email.ocrMarkdownPaths && email.ocrMarkdownPaths.length > 0 && (
        <div className="attachments-section">
          <h3>OCR Extracted Content</h3>
          {email.ocrMarkdownPaths.map((ocr, i) => (
            <div className="attachment-row" key={i}>
              <div className="att-info">
                <span className="badge">ocr</span>
                <span className="att-name">{ocr.original}</span>
              </div>
              <div className="attachment-actions">
                <a
                  className="btn primary"
                  href={`/api/ocr/markdown?path=${encodeURIComponent(ocr.path)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View extracted markdown
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
