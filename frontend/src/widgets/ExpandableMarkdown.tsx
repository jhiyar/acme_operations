import { useEffect, useId, useState } from "react";

import { Markdown } from "./Markdown";

type ExpandableMarkdownProps = {
  children: string;
  className?: string;
  /** Approx. character length before offering expand. */
  previewChars?: number;
  /** Collapsed visual height in px. */
  collapsedMaxHeight?: number;
};

export function ExpandableMarkdown({
  children,
  className = "",
  previewChars = 420,
  collapsedMaxHeight = 168,
}: ExpandableMarkdownProps) {
  const contentId = useId();
  const [expanded, setExpanded] = useState(false);
  const needsToggle = children.trim().length > previewChars;

  useEffect(() => {
    setExpanded(false);
  }, [children]);

  if (!children.trim()) {
    return <p className="muted">—</p>;
  }

  return (
    <div className={`expandable-block ${className}`.trim()}>
      <div
        id={contentId}
        className={`expandable-body${needsToggle && !expanded ? " is-collapsed" : ""}`}
        style={
          needsToggle && !expanded
            ? { maxHeight: collapsedMaxHeight }
            : undefined
        }
      >
        <Markdown>{children}</Markdown>
      </div>
      {needsToggle ? (
        <button
          type="button"
          className="btn-link-more"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Show less" : "Show more…"}
        </button>
      ) : null}
    </div>
  );
}
