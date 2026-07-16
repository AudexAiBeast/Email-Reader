import { useState } from "react";
import { graphqlQuery } from "../api.js";

const SUMMARY_QUERY = `
  query EmailSummary($emailId: Int!) {
    emailSummary(emailId: $emailId)
  }
`;

export default function AiSummary({ emailId, existingSummary }) {
  const [summary, setSummary] = useState(existingSummary || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const data = await graphqlQuery(SUMMARY_QUERY, { emailId });
      setSummary(data.emailSummary);
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
        <div className="ai-summary-body">{summary}</div>
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 8 }}>
          Summarized by audAInsights
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
        <div className="ai-summary-loading">Generating summary with Ollama...</div>
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
          Failed: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="ai-summary">
      <div className="ai-summary-header">
        <span className="ai-badge">AI</span>
        audAInsights Summary
      </div>
      <div className="ai-summary-generate" onClick={generate}>
        Generate summary with AI
      </div>
    </div>
  );
}
