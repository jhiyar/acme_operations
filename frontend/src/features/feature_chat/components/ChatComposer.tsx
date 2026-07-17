import type { FormEvent, ReactNode } from "react";

type ChatComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  trailing?: ReactNode;
};

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder = "Ask about a customer, issue, or next action…",
  trailing,
}: ChatComposerProps) {
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!value.trim() || disabled) {
      return;
    }
    onSubmit();
  };

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={2}
        disabled={disabled}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (value.trim() && !disabled) {
              onSubmit();
            }
          }
        }}
      />
      <div className="composer-actions">
        {trailing}
        <button type="submit" className="btn btn-primary" disabled={disabled || !value.trim()}>
          Send
        </button>
      </div>
    </form>
  );
}
