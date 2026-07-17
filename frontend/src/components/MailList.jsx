import { useEffect, useState } from "react";
import { graphqlQuery } from "../api.js";
import MailDetail from "./MailDetail.jsx";

const EMAILS_QUERY = `
  query Emails(
    $dateFrom: Date
    $dateTo: Date
    $sender: String
    $subjectContains: String
    $hasAttachments: Boolean
    $companyName: String
    $limit: Int
    $offset: Int
  ) {
    emails(
      dateFrom: $dateFrom
      dateTo: $dateTo
      sender: $sender
      subjectContains: $subjectContains
      hasAttachments: $hasAttachments
      companyName: $companyName
      limit: $limit
      offset: $offset
      orderBy: DATE_DESC
    ) {
      totalCount
      hasMore
      items {
        id
        messageId
        fromAddress
        subject
        emailDate
        hasAttachments
        attachmentCount
        companyName
      }
    }
  }
`;

const SINGLE_EMAIL_QUERY = `
  query Email($messageId: String!) {
    email(messageId: $messageId) {
      id
      messageId
      fromAddress
      toAddress
      ccAddress
      bccAddress
      subject
      dateRaw
      emailDate
      bodyText
      bodyHtml
      hasAttachments
      attachmentCount
      companyName
      companyDomainSource
      companySignatureSource
      aiSummary
      attachments {
        category
        index
        filename
        ftpPath
      }
      ocrMarkdownPaths {
        filename
        path
        original
      }
    }
  }
`;

const PAGE_SIZE = 50;

export default function MailList({ companyName }) {
  const [filters, setFilters] = useState({
    sender: "",
    subjectContains: "",
    dateFrom: "",
    dateTo: "",
    hasAttachments: false,
  });
  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedEmail, setSelectedEmail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function runSearch(nextOffset = 0) {
    setLoading(true);
    setError(null);
    try {
      const data = await graphqlQuery(EMAILS_QUERY, {
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        sender: filters.sender || null,
        subjectContains: filters.subjectContains || null,
        hasAttachments: filters.hasAttachments ? true : null,
        companyName: companyName || null,
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      setItems(data.emails.items);
      setTotalCount(data.emails.totalCount);
      setOffset(nextOffset);
      if (data.emails.items.length && selectedId == null) {
        setSelectedId(data.emails.items[0].id);
        fetchSingleEmail(data.emails.items[0].messageId);
      } else if (data.emails.items.length === 0) {
        setSelectedEmail(null);
        setSelectedId(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function fetchSingleEmail(messageId) {
    try {
      const data = await graphqlQuery(SINGLE_EMAIL_QUERY, { messageId });
      setSelectedEmail(data.email);
    } catch (err) {
      setSelectedEmail(null);
    }
  }

  useEffect(() => {
    setSelectedId(null);
    setSelectedEmail(null);
    setOffset(0);
    runSearch(0);
  }, [companyName]);

  function onFilterChange(key, value) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  function selectEmail(item) {
    setSelectedId(item.id);
    setSelectedEmail(null);
    fetchSingleEmail(item.messageId);
  }

  return (
    <div className="three-pane">
      <div className="pane-list">
        <div className="main-toolbar" style={{ borderRight: "none", padding: "10px 12px" }}>
          <input
            type="text"
            placeholder="Sender..."
            value={filters.sender}
            onChange={(e) => onFilterChange("sender", e.target.value)}
          />
          <input
            type="text"
            placeholder="Subject..."
            value={filters.subjectContains}
            onChange={(e) => onFilterChange("subjectContains", e.target.value)}
          />
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(e) => onFilterChange("dateFrom", e.target.value)}
          />
          <label>
            <input
              type="checkbox"
              checked={filters.hasAttachments}
              onChange={(e) => onFilterChange("hasAttachments", e.target.checked)}
            />
            Att.
          </label>
          <button className="btn primary" onClick={() => runSearch(0)} disabled={loading}>
            {loading ? "..." : "Go"}
          </button>
        </div>

        {error && <div className="empty-state">Error: {error}</div>}

        <div className="email-list">
          {items.map((item) => (
            <div
              key={item.id}
              className={`email-row${selectedId === item.id ? " selected" : ""}`}
              onClick={() => selectEmail(item)}
            >
              <div className="email-sender">{item.fromAddress || "-"}</div>
              <div className="email-subject">{item.subject || "(no subject)"}</div>
              <div className="email-meta">
                <span>{item.companyName || "Uncategorized"}</span>
                <span className="email-date">
                  {item.emailDate ? item.emailDate.replace("T", " ").slice(0, 16) : "-"}
                </span>
                {item.hasAttachments && (
                  <span className="email-attachment-badge">📎 {item.attachmentCount}</span>
                )}
              </div>
            </div>
          ))}
          {!items.length && !loading && (
            <div className="empty-state">No emails found.</div>
          )}
        </div>

        <div className="pagination">
          <span>
            {totalCount > 0
              ? `${offset + 1}–${Math.min(offset + items.length, totalCount)} of ${totalCount}`
              : "No results"}
          </span>
          <div className="pagination-actions">
            <button
              className="btn"
              disabled={offset === 0 || loading}
              onClick={() => runSearch(Math.max(0, offset - PAGE_SIZE))}
            >
              Prev
            </button>
            <button
              className="btn"
              disabled={offset + items.length >= totalCount || loading}
              onClick={() => runSearch(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div className="pane-detail">
        {selectedEmail ? (
          <MailDetail key={selectedEmail.id} email={selectedEmail} />
        ) : selectedId ? (
          <div className="empty-state">Loading email...</div>
        ) : (
          <div className="empty-state">Select an email to view its content.</div>
        )}
      </div>
    </div>
  );
}
