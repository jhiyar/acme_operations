import { useState } from "react";

import { useIssues } from "./hooks/useIssues";
import { useAuth } from "../core/AuthProvider";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

export function IssuesPage() {
  const { user } = useAuth();
  const isAdmin = user?.roles.includes("admin") ?? false;
  const [status, setStatus] = useState("");
  const { data, isLoading, isError, error, refetch, isFetching } = useIssues({
    status: status || undefined,
  });

  return (
    <div className="issues-page">
      <section className="issues-content">
        <header className="issues-header">
          <div className="issues-header-main">
            <h1>Issues</h1>
            <div className="issues-header-controls">
              <label className="filter-field compact">
                <span className="sr-only">Status</span>
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  aria-label="Filter by status"
                >
                  {STATUS_OPTIONS.map((option) => (
                    <option key={option.value || "all"} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="btn btn-ghost btn-compact"
                onClick={() => void refetch()}
                disabled={isFetching}
              >
                Refresh
              </button>
            </div>
          </div>
          <p className="muted issues-subtitle">
            {isAdmin
              ? "Admin view — all customer issues across the organisation."
              : "Your assigned issues only."}{" "}
            · Scope: {data?.scope === "all" ? "everyone" : "assigned to you"} ·{" "}
            {data?.count ?? 0} issues
          </p>
        </header>

        {isLoading ? <p className="muted">Loading issues…</p> : null}
        {isError ? (
          <p className="error">
            {error instanceof Error ? error.message : "Failed to load issues"}
          </p>
        ) : null}

        {!isLoading && data && data.issues.length === 0 ? (
          <div className="chat-empty">
            <p>No issues in this view.</p>
            <p className="muted">
              Try another status filter, or ask the assistant about a customer.
            </p>
          </div>
        ) : null}

        <div className="issue-list">
          {data?.issues.map((issue) => (
            <article key={issue.id} className="issue-row">
              <div className="issue-row-top">
                <h2>
                  <span className="issue-id">#{issue.id}</span> {issue.title}
                </h2>
                <div className="issue-badges">
                  <span className={`badge status-${issue.status}`}>{issue.status}</span>
                  <span className={`badge priority-${issue.priority}`}>
                    {issue.priority}
                  </span>
                </div>
              </div>
              <p className="issue-meta">
                {issue.customer.name} · assigned to {issue.assigned_to}
              </p>
              {issue.description ? (
                <p className="issue-desc">{issue.description}</p>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
