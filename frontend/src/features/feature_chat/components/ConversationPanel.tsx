type ConversationPanelProps = {
  open: boolean;
  onClose: () => void;
  conversations: Array<{
    id: string;
    title: string;
    updated_at: string;
    message_count: number;
  }>;
  activeId: string | null;
  loading?: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
};

function formatUpdatedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ConversationPanel({
  open,
  onClose,
  conversations,
  activeId,
  loading,
  onSelect,
  onNew,
  onDelete,
}: ConversationPanelProps) {
  if (!open) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        className="conversation-backdrop"
        aria-label="Close conversations"
        onClick={onClose}
      />
      <aside className="conversation-panel" aria-label="Conversations">
        <header className="conversation-panel-header">
          <h2>Conversations</h2>
          <button type="button" className="btn btn-ghost btn-compact" onClick={onNew}>
            New
          </button>
        </header>

        {loading ? <p className="muted conversation-empty">Loading…</p> : null}

        {!loading && conversations.length === 0 ? (
          <p className="muted conversation-empty">No conversations yet.</p>
        ) : null}

        <ul className="conversation-list">
          {conversations.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`conversation-item${activeId === item.id ? " is-active" : ""}`}
                onClick={() => onSelect(item.id)}
              >
                <span className="conversation-item-title">{item.title}</span>
                <span className="conversation-item-meta muted">
                  {formatUpdatedAt(item.updated_at)}
                  {item.message_count
                    ? ` · ${item.message_count} message${item.message_count === 1 ? "" : "s"}`
                    : ""}
                </span>
              </button>
              <button
                type="button"
                className="conversation-delete"
                aria-label={`Delete ${item.title}`}
                onClick={() => onDelete(item.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </>
  );
}
