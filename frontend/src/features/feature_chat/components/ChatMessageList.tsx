import { Markdown } from "../../../widgets/Markdown";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolsUsed?: string[];
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
          Example: “For Contoso’s production-line alert noise issue: summarise the
          history and recommend a next action. Also list Contoso’s open issues.”
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
          {message.role === "assistant" ? (
            <Markdown className="bubble-body">{message.content}</Markdown>
          ) : (
            <p className="bubble-body bubble-body-plain">{message.content}</p>
          )}
          {message.toolsUsed?.length ? (
            <p className="bubble-tools muted">
              Tools: {message.toolsUsed.join(" → ")}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
