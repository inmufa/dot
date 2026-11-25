import { ChevronDown } from "lucide-react";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

interface FieldProps {
  label: string;
  help?: ReactNode;
  error?: ReactNode;
  children: ReactNode | ((p: { id: string; "aria-describedby": string | undefined; "aria-invalid": true | undefined }) => ReactNode);
}

/** Label + control + help/error. Pass a render function to wire id and aria automatically. */
export function Field({ label, help, error, children }: FieldProps) {
  const id = useId();
  const note = error ? `${id}-e` : help ? `${id}-h` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {typeof children === "function" ? children({ id, "aria-describedby": note, "aria-invalid": error ? true : undefined }) : children}
      {error ? <p id={`${id}-e`} className="help field-error" role="alert">{error}</p> : help ? <p id={`${id}-h`} className="help">{help}</p> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={`input${className ? ` ${className}` : ""}`} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, rows = 3, ...rest }, ref) {
  return <textarea ref={ref} rows={rows} className={`input input-area${className ? ` ${className}` : ""}`} {...rest} />;
});

/** Native select (best on touch and for a11y) with the shared look. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...rest }, ref) {
  return (
    <span className="select">
      <select ref={ref} className={`input${className ? ` ${className}` : ""}`} {...rest}>{children}</select>
      <ChevronDown size={16} aria-hidden />
    </span>
  );
});
