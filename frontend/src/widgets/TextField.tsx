import type { InputHTMLAttributes } from "react";
import { forwardRef } from "react";

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField({ label, error, id, className = "", ...props }, ref) {
    const fieldId = id ?? props.name ?? label.toLowerCase().replace(/\s+/g, "-");

    return (
      <label className={`text-field ${className}`.trim()} htmlFor={fieldId}>
        <span>{label}</span>
        <input id={fieldId} ref={ref} {...props} />
        {error ? <span className="field-error">{error}</span> : null}
      </label>
    );
  },
);
