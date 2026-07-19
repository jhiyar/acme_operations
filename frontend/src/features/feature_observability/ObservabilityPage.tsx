import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getAgentRun, listAgentRuns } from "../../services/ObservabilityService";
import { ExpandableMarkdown } from "../../widgets/ExpandableMarkdown";
import { PrettyJson } from "../../widgets/PrettyJson";

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function ObservabilityPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const runsQuery = useQuery({
    queryKey: ["admin-runs"],
    queryFn: () => listAgentRuns(75),
  });
  const detailQuery = useQuery({
    queryKey: ["admin-run", selectedId],
    queryFn: () => getAgentRun(selectedId!),
    enabled: Boolean(selectedId),
  });

  return (
    <div className="observability-page">
      <section className="observability-content">
        <header className="issues-header">
          <div className="issues-header-main">
            <h1>Observability</h1>
            <button
              type="button"
              className="btn btn-ghost btn-compact"
              onClick={() => void runsQuery.refetch()}
              disabled={runsQuery.isFetching}
            >
              Refresh
            </button>
          </div>
          <p className="muted issues-subtitle">
            Admin view of agent runs — LLM calls, tool usage, and token counts.
          </p>
        </header>

        {runsQuery.isLoading ? <p className="muted">Loading runs…</p> : null}
        {runsQuery.isError ? (
          <p className="error">Failed to load agent runs.</p>
        ) : null}

        <div className="observability-layout">
          <div className="run-list">
            {(runsQuery.data?.runs ?? []).map((run) => (
              <button
                key={run.id}
                type="button"
                className={`run-row${selectedId === run.id ? " is-active" : ""}`}
                onClick={() => setSelectedId(run.id)}
              >
                <div className="run-row-top">
                  <strong>{run.username || "user"}</strong>
                  <span className="muted">{formatTime(run.created_at)}</span>
                </div>
                <p className="run-row-message">{run.user_message}</p>
                <p className="run-row-meta muted">
                  {run.total_tokens} tok · {run.tool_count} tools ·{" "}
                  {run.latency_ms ?? "—"} ms
                  {run.error ? " · error" : ""}
                </p>
              </button>
            ))}
            {!runsQuery.isLoading && (runsQuery.data?.runs.length ?? 0) === 0 ? (
              <div className="chat-empty">
                <p>No agent runs yet.</p>
                <p className="muted">Send a chat message to create the first trace.</p>
              </div>
            ) : null}
          </div>

          <aside className="run-detail">
            {!selectedId ? (
              <p className="muted">Select a run to inspect LLM and tool activity.</p>
            ) : null}
            {detailQuery.isLoading ? <p className="muted">Loading detail…</p> : null}
            {detailQuery.data ? (
              <div className="run-detail-card">
                <h2>Run detail</h2>
                <p className="muted">
                  {detailQuery.data.provider}/{detailQuery.data.model} ·{" "}
                  {detailQuery.data.prompt_tokens} in / {detailQuery.data.completion_tokens}{" "}
                  out / {detailQuery.data.total_tokens} total ·{" "}
                  {detailQuery.data.llm_call_count} LLM calls
                </p>
                <h3>User</h3>
                <ExpandableMarkdown
                  className="run-markdown"
                  previewChars={280}
                  collapsedMaxHeight={96}
                >
                  {detailQuery.data.user_message}
                </ExpandableMarkdown>
                <h3>Assistant</h3>
                <ExpandableMarkdown className="run-markdown">
                  {detailQuery.data.assistant_reply || detailQuery.data.error || "—"}
                </ExpandableMarkdown>

                <h3>LLM calls</h3>
                {detailQuery.data.llm_calls.length === 0 ? (
                  <p className="muted">No LLM calls recorded.</p>
                ) : (
                  <ul className="run-sublist">
                    {detailQuery.data.llm_calls.map((call) => (
                      <li key={call.id}>
                        <strong>{call.purpose}</strong> · {call.provider}/{call.model} ·{" "}
                        {call.total_tokens} tok · {call.latency_ms ?? "—"} ms
                      </li>
                    ))}
                  </ul>
                )}

                <h3>Tool calls</h3>
                {detailQuery.data.tool_calls.length === 0 ? (
                  <p className="muted">No tools used.</p>
                ) : (
                  <ul className="run-sublist">
                    {detailQuery.data.tool_calls.map((call) => (
                      <li key={call.id}>
                        <strong>{call.tool}</strong>
                        <PrettyJson
                          className="compact"
                          label="Args"
                          value={call.args}
                          previewChars={180}
                          collapsedMaxHeight={96}
                        />
                        {call.result_preview ? (
                          <PrettyJson
                            className="compact"
                            label="Result"
                            value={call.result_preview}
                            previewChars={220}
                            collapsedMaxHeight={120}
                          />
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}
          </aside>
        </div>
      </section>
    </div>
  );
}
