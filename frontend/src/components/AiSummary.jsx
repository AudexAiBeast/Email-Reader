import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { graphqlQuery } from "../api.js";

const SUMMARY_QUERY = `
  query EmailSummary($emailId: Int!) {
    emailSummary(emailId: $emailId)
  }
`;

const DEBOUNCE_MS = 800;

const SKIP_COMPANIES = ["System Notifications"];

export default function AiSummary({ emailId, existingSummary, companyName }) {
  const [summary, setSummary] = useState(existingSummary || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fetchedRef = useRef(false);
  const debounceRef = useRef(null);

  const skipReason = companyName && SKIP_COMPANIES.includes(companyName)
    ? `${companyName} emails are system-generated and not summarized`
    : null;

  useEffect(() => {
    setSummary(existingSummary || null);
    setError(null);
    fetchedRef.current = false;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!existingSummary && emailId != null && !skipReason) {
      debounceRef.current = setTimeout(() => autoGenerate(), DEBOUNCE_MS);
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [emailId]);

  async function autoGenerate() {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const data = await graphqlQuery(SUMMARY_QUERY, { emailId });
      setSummary(data.emailSummary);
      if (!data.emailSummary) {
        setError("Ollama not available or no content to summarize");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (summary) {
    return (
      <div className="ai-summary">
        <div className="ai-summary-header">
          <span className="ai-badge">AI</span>
          audAInsights Summary
        </div>
        <div className="ai-summary-body markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {summary}
          </ReactMarkdown>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
          Summarized by audAInsights
        </div>
      </div>
    );
  }

  if (skipReason) {
    return (
      <div className="ai-summary">
        <div className="ai-summary-header">
          <span className="ai-badge">AI</span>
          audAInsights Summary
        </div>
        <div className="ai-summary-body" style={{ color: "var(--text-dim)", fontStyle: "italic" }}>
          {skipReason}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="ai-summary">
        <div className="ai-summary-header">
          <span className="ai-badge">AI</span>
          audAInsights Summary
        </div>
        <div className="ai-summary-loading">
          <span className="spinner" />
          Generating summary with Ollama...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ai-summary">
        <div className="ai-summary-header">
          <span className="ai-badge">AI</span>
          audAInsights Summary
        </div>
        <div className="ai-summary-body" style={{ color: "var(--error)" }}>
          {error}
        </div>
      </div>
    );
  }

  return null;
}
