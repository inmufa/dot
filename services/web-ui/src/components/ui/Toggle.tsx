import { Check, Minus } from "lucide-react";
import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "children"> { children?: ReactNode; description?: ReactNode }

function Row({ kind, children, description, className, ...rest }: Props & { kind: "switch" | "checkbox" | "radio" }, ref: React.Ref<HTMLInputElement>) {
  return (
    <label className={`tg tg-${kind}${className ? ` ${className}` : ""}`}>
      <input ref={ref} type={kind === "switch" ? "checkbox" : kind} role={kind === "switch" ? "switch" : undefined} {...rest} />
      <span className="tg-box" aria-hidden>
        {kind === "switch" && <span className="tg-knob" />}
        {kind === "checkbox" && <><Check size={12} strokeWidth={3} className="tg-check" /><Minus size={12} strokeWidth={3} className="tg-mixed" /></>}
        {kind === "radio" && <span className="tg-dot" />}
      </span>
      {(children || description) && (
        <span className="tg-text">
          {children}
          {description && <span className="tg-desc">{description}</span>}
        </span>
      )}
    </label>
  );
}

/** Switch: role=switch on a native checkbox, so forms and keyboard work for free. */
export const Switch = forwardRef<HTMLInputElement, Props>((p, r) => Row({ ...p, kind: "switch" }, r));
Switch.displayName = "Switch";
export const Checkbox = forwardRef<HTMLInputElement, Props>((p, r) => Row({ ...p, kind: "checkbox" }, r));
Checkbox.displayName = "Checkbox";
export const Radio = forwardRef<HTMLInputElement, Props>((p, r) => Row({ ...p, kind: "radio" }, r));
Radio.displayName = "Radio";
