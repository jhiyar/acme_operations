import { useEffect, useId, useMemo, useState } from "react";

type PrettyJsonProps = {
  value: unknown;
  className?: string;
  previewChars?: number;
  collapsedMaxHeight?: number;
  label?: string;
};

function formatJson(value: unknown): string {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return "";
    }
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      // Truncated / invalid JSON — still break onto readable lines when possible.
      if (trimmed.includes("\n")) {
        return trimmed;
      }
      return trimmed
        .replace(/,(?=\s*")/g, ",\n")
        .replace(/\{/g, "{\n")
        .replace(/\}/g, "\n}")
        .replace(/\[/g, "[\n")
        .replace(/\]/g, "\n]");
    }
  }
  try {
    return JSON.stringify(value ?? null, null, 2);
  } catch {
    return String(value);
  }
}

/** Lightweight token coloring for pretty-printed JSON. */
function highlightJson(text: string) {
  const pattern =
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;

  const nodes: Array<string | { className: string; text: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const [full, quoted, colon, literal] = match;
    if (quoted !== undefined) {
      nodes.push({
        className: colon ? "json-key" : "json-string",
        text: full,
      });
    } else if (literal !== undefined) {
      nodes.push({ className: "json-literal", text: full });
    } else {
      nodes.push({ className: "json-number", text: full });
    }
    lastIndex = match.index + full.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

export function PrettyJson({
  value,
  className = "",
  previewChars = 280,
  collapsedMaxHeight = 140,
  label,
}: PrettyJsonProps) {
  const contentId = useId();
  const [expanded, setExpanded] = useState(false);
  const formatted = useMemo(() => formatJson(value), [value]);
  const tokens = useMemo(() => highlightJson(formatted), [formatted]);
  const needsToggle = formatted.length > previewChars;

  useEffect(() => {
    setExpanded(false);
  }, [formatted]);

  if (!formatted) {
    return null;
  }

  return (
    <div className={`pretty-json ${className}`.trim()}>
      {label ? <span className="pretty-json-label muted">{label}</span> : null}
      <pre
        id={contentId}
        className={`pretty-json-body${needsToggle && !expanded ? " is-collapsed" : ""}`}
        style={
          needsToggle && !expanded
            ? { maxHeight: collapsedMaxHeight }
            : undefined
        }
      >
        <code>
          {tokens.map((token, index) =>
            typeof token === "string" ? (
              <span key={index}>{token}</span>
            ) : (
              <span key={index} className={token.className}>
                {token.text}
              </span>
            ),
          )}
        </code>
      </pre>
      {needsToggle ? (
        <button
          type="button"
          className="btn-link-more"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? "Show less" : "Show more…"}
        </button>
      ) : null}
    </div>
  );
}
