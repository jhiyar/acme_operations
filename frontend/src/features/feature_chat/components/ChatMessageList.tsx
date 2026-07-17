export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatMessageListProps = {
  messages: ChatMessage[];
};

export function ChatMessageList({ messages }: ChatMessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <p>Ask a question to get started.</p>
        <p className="muted">
          Example: “Show me open issues for Client X and suggest the next action.”
        </p>
      </div>
    );
  }

  return (
    <div className="chat-messages" role="log" aria-live="polite">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`chat-bubble chat-bubble-${message.role}`}
        >
          <span className="bubble-label">
            {message.role === "user" ? "You" : "Assistant"}
          </span>
          <p>{message.content}</p>
        </article>
      ))}
    </div>
  );
}
