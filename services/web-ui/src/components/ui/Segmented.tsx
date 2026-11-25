import { useId, type ReactNode } from "react";

interface Option<T extends string> { value: T; label: ReactNode; title?: string; disabled?: boolean }
interface Props<T extends string> { value: T; onChange: (v: T) => void; options: Option<T>[]; label: string; size?: "sm" | "md" }

/** Native radio group styled as a segmented control; the selected segment is a raised tone. */
export function Segmented<T extends string>({ value, onChange, options, label, size = "md" }: Props<T>) {
  const name = useId();
  return (
    <div className="seg" role="radiogroup" aria-label={label} data-size={size}>
      {options.map((o) => (
        <label key={o.value} title={o.title} data-disabled={o.disabled || undefined}>
          <input type="radio" name={name} value={o.value} checked={value === o.value} disabled={o.disabled} onChange={() => onChange(o.value)} />
          <span>{o.label}</span>
        </label>
      ))}
    </div>
  );
}
