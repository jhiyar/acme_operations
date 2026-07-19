import type { ReactNode } from "react";
import { useEffect } from "react";

type CustomModalProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

export function CustomModal({ open, title, onClose, children }: CustomModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="custom-modal" role="presentation">
      <button
        type="button"
        className="custom-modal-backdrop"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <div
        className="custom-modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="custom-modal-title"
      >
        <header className="custom-modal-header">
          <h2 id="custom-modal-title">{title}</h2>
          <button
            type="button"
            className="btn btn-ghost btn-compact"
            onClick={onClose}
            aria-label="Close"
          >
            Close
          </button>
        </header>
        <div className="custom-modal-body">{children}</div>
      </div>
    </div>
  );
}
