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
    $limit: Int
    $offset: Int
  ) {
    emails(
      dateFrom: $dateFrom
      dateTo: $dateTo
      sender: $sender
      subjectContains: $subjectContains
      hasAttachments: $hasAttachments
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
        toAddress
        ccAddress
        bccAddress
        replyTo
        subject
        dateRaw
        emailDate
        mailDate
        bodyText
        bodyHtml
        hasAttachments
        attachmentCount
        attachments {
          category
          index
          filename
          ftpPath
        }
        createdAt
      }
    }
  }
`;

const PAGE_SIZE = 50;

export default function MailList() {
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    sender: "",
    subjectContains: "",
    hasAttachments: false,
  });
  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
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
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      setItems(data.emails.items);
      setTotalCount(data.emails.totalCount);
      setOffset(nextOffset);
      if (data.emails.items.length && !selected) {
        setSelected(data.emails.items[0]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runSearch(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onFilterChange(key, value) {
    setFilters((f) => ({ ...f, [key]: value }));
  }

  return (
    <div>
      <div className="toolbar">
        <input
          type="text"
          placeholder="Sender contains..."
          value={filters.sender}
          onChange={(e) => onFilterChange("sender", e.target.value)}
        />
        <input
          type="text"
          placeholder="Subject contains..."
          value={filters.subjectContains}
          onChange={(e) => onFilterChange("subjectContains", e.target.value)}
        />
        <input
          type="date"
          value={filters.dateFrom}
          onChange={(e) => onFilterChange("dateFrom", e.target.value)}
        />
        <span style={{ color: "var(--text-dim)" }}>to</span>
        <input
          type="date"
          value={filters.dateTo}
          onChange={(e) => onFilterChange("dateTo", e.target.value)}
        />
        <label>
          <input
            type="checkbox"
            checked={filters.hasAttachments}
            onChange={(e) => onFilterChange("hasAttachments", e.target.checked)}
          />
          Has attachments
        </label>
        <button className="btn primary" onClick={() => runSearch(0)} disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
        <span className="badge">{totalCount} total</span>
      </div>

      {error && <div className="empty-state">Error: {error}</div>}

      <div className="split">
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>From</th>
                <th>Subject</th>
                <th>Att.</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={selected && selected.id === item.id ? "selected" : ""}
                  onClick={() => setSelected(item)}
                >
                  <td>{item.emailDate ? item.emailDate.replace("T", " ").slice(0, 16) : "-"}</td>
                  <td>{item.fromAddress || "-"}</td>
                  <td>{item.subject || "(no subject)"}</td>
                  <td>{item.hasAttachments ? `📎 ${item.attachmentCount}` : ""}</td>
                </tr>
              ))}
              {!items.length && !loading && (
                <tr>
                  <td colSpan={4} className="empty-state">
                    No emails found. Once mail starts ingesting, it'll show up here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="toolbar" style={{ padding: "10px 12px" }}>
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

        <div className="panel">
          {selected ? (
            <MailDetail email={selected} />
          ) : (
            <div className="empty-state">Select an email to view its content.</div>
          )}
        </div>
      </div>
    </div>
  );
}
