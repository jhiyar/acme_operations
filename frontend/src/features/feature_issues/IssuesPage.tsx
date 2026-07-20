import { useState } from "react";

import { Button } from "../../widgets/Button";
import { CustomModal } from "../../widgets/CustomModal";
import {
  ADMIN_ROLES,
  ISSUE_UPDATE_ROLES,
  PermissionCheck,
  useHasRole,
} from "../../widgets/PermissionCheck";
import { IssueForm } from "./components/IssueForm";
import {
  useAddIssueUpdate,
  useDeleteIssue,
  useDeleteIssueUpdate,
  useUpdateIssue,
} from "./hooks/useIssueMutations";
import { useIssues, type Issue } from "./hooks/useIssues";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

const EDITABLE_STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

function IssueRow({
  issue,
  onEdit,
  onDelete,
}: {
  issue: Issue;
  onEdit: (issueId: number) => void;
  onDelete: (issue: Issue) => void;
}) {
  const [note, setNote] = useState("");
  const updateIssue = useUpdateIssue();
  const addUpdate = useAddIssueUpdate();
  const deleteUpdate = useDeleteIssueUpdate();
  const busy =
    updateIssue.isPending || addUpdate.isPending || deleteUpdate.isPending;

  return (
    <article className="issue-row">
      <div className="issue-row-top">
        <h2>
          <span className="issue-id">#{issue.id}</span> {issue.title}
        </h2>
        <div className="issue-badges">
          <span className={`badge status-${issue.status}`}>{issue.status}</span>
          <span className={`badge priority-${issue.priority}`}>{issue.priority}</span>
        </div>
      </div>
      <p className="issue-meta">
        {issue.customer.name} · assigned to {issue.assigned_to}
      </p>
      {issue.description ? <p className="issue-desc">{issue.description}</p> : null}

      {issue.updates && issue.updates.length > 0 ? (
        <ul className="issue-timeline">
          {issue.updates.map((update) => (
            <li key={update.id}>
              <div className="issue-timeline-main">
                <span className="issue-timeline-meta">
                  {update.author} · {new Date(update.created_at).toLocaleString()}
                </span>
                <span className="issue-timeline-body">{update.body}</span>
              </div>
              <PermissionCheck roles={ISSUE_UPDATE_ROLES}>
                <button
                  type="button"
                  className="btn btn-ghost btn-compact issue-delete"
                  disabled={busy}
                  aria-label={`Delete note by ${update.author}`}
                  onClick={() => {
                    if (
                      !window.confirm(
                        "Delete this timeline note? This cannot be undone.",
                      )
                    ) {
                      return;
                    }
                    deleteUpdate.mutate({
                      issueId: issue.id,
                      updateId: update.id,
                    });
                  }}
                >
                  Delete
                </button>
              </PermissionCheck>
            </li>
          ))}
        </ul>
      ) : null}

      <PermissionCheck roles={ADMIN_ROLES}>
        <div className="issue-manage">
          <button
            type="button"
            className="btn btn-ghost btn-compact"
            disabled={busy}
            onClick={() => onEdit(issue.id)}
          >
            Edit
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-compact issue-delete"
            disabled={busy}
            onClick={() => onDelete(issue)}
          >
            Delete
          </button>
        </div>
      </PermissionCheck>

      <PermissionCheck roles={ISSUE_UPDATE_ROLES}>
        <div className="issue-edit">
          <label className="filter-field compact">
            <span className="sr-only">Update status</span>
            <select
              value={issue.status}
              disabled={busy}
              aria-label={`Status for issue ${issue.id}`}
              onChange={(event) => {
                const next = event.target.value;
                if (next === issue.status) {
                  return;
                }
                updateIssue.mutate({ issueId: issue.id, status: next });
              }}
            >
              {EDITABLE_STATUSES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <form
            className="issue-note-form"
            onSubmit={(event) => {
              event.preventDefault();
              const body = note.trim();
              if (!body || busy) {
                return;
              }
              addUpdate.mutate(
                { issueId: issue.id, body },
                { onSuccess: () => setNote("") },
              );
            }}
          >
            <input
              type="text"
              value={note}
              disabled={busy}
              placeholder="Add a timeline note…"
              aria-label={`Note for issue ${issue.id}`}
              onChange={(event) => setNote(event.target.value)}
            />
            <button
              type="submit"
              className="btn btn-ghost btn-compact"
              disabled={busy || !note.trim()}
            >
              Post
            </button>
          </form>
          {updateIssue.isError || addUpdate.isError ? (
            <p className="error issue-edit-error">Update failed — check permissions.</p>
          ) : null}
        </div>
      </PermissionCheck>
    </article>
  );
}

export function IssuesPage() {
  const isAdmin = useHasRole(ADMIN_ROLES);
  const canUpdate = useHasRole(ISSUE_UPDATE_ROLES);
  const [status, setStatus] = useState("");
  const [modalIssueId, setModalIssueId] = useState<number | null | undefined>(
    undefined,
  );
  const [issueToDelete, setIssueToDelete] = useState<Issue | null>(null);
  const deleteIssue = useDeleteIssue();
  const { data, isLoading, isError, error, refetch, isFetching } = useIssues({
    status: status || undefined,
  });

  const modalOpen = modalIssueId !== undefined;
  const isCreate = modalIssueId === null;

  const closeDeleteDialog = () => {
    if (deleteIssue.isPending) {
      return;
    }
    setIssueToDelete(null);
    deleteIssue.reset();
  };

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
              <PermissionCheck roles={ADMIN_ROLES}>
                <button
                  type="button"
                  className="btn btn-primary btn-compact"
                  onClick={() => setModalIssueId(null)}
                >
                  New issue
                </button>
              </PermissionCheck>
            </div>
          </div>
          <p className="muted issues-subtitle">
            {isAdmin
              ? "Admin view — create, edit, and delete issues across the organisation."
              : canUpdate
                ? "Support view — update status and post notes on assigned issues."
                : "Sales view — assigned issues only (read-only)."}{" "}
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
            <IssueRow
              key={issue.id}
              issue={issue}
              onEdit={(issueId) => setModalIssueId(issueId)}
              onDelete={setIssueToDelete}
            />
          ))}
        </div>
      </section>

      <PermissionCheck roles={ADMIN_ROLES}>
        <CustomModal
          open={modalOpen}
          title={isCreate ? "New issue" : `Edit issue #${modalIssueId}`}
          onClose={() => setModalIssueId(undefined)}
        >
          <IssueForm
            id={modalIssueId}
            onCancel={() => setModalIssueId(undefined)}
            onSuccess={() => setModalIssueId(undefined)}
          />
        </CustomModal>

        <CustomModal
          open={issueToDelete != null}
          title="Delete issue"
          onClose={closeDeleteDialog}
        >
          {issueToDelete ? (
            <div className="confirm-dialog">
              <p>
                Delete issue #{issueToDelete.id} “{issueToDelete.title}”? This cannot
                be undone.
              </p>
              {deleteIssue.isError ? (
                <p className="error">Delete failed — check permissions and try again.</p>
              ) : null}
              <div className="issue-form-actions">
                <Button
                  type="button"
                  variant="ghost"
                  disabled={deleteIssue.isPending}
                  onClick={closeDeleteDialog}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  disabled={deleteIssue.isPending}
                  onClick={() => {
                    deleteIssue.mutate(issueToDelete.id, {
                      onSuccess: () => {
                        setIssueToDelete(null);
                        deleteIssue.reset();
                      },
                    });
                  }}
                >
                  {deleteIssue.isPending ? "Deleting…" : "Delete"}
                </Button>
              </div>
            </div>
          ) : null}
        </CustomModal>
      </PermissionCheck>
    </div>
  );
}
