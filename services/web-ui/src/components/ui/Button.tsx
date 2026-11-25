import { Tooltip } from "./Tooltip";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "solid" | "soft" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";
const CLS: Record<ButtonVariant, string> = { solid: "btn btn-primary", soft: "btn", ghost: "btn btn-ghost", danger: "btn btn-danger" };

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  /** Keeps width, shows a spinner, blocks clicks. */
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "soft", size = "md", icon, loading, className, children, disabled, type = "button", ...rest }, ref) {
  return (
    <button ref={ref} type={type} className={`${CLS[variant]} btn-${size}${className ? ` ${className}` : ""}`} disabled={disabled} aria-busy={loading || undefined} data-loading={loading || undefined} {...rest} onClick={loading ? undefined : rest.onClick}>
      {icon && <span className="btn-ic" aria-hidden>{icon}</span>}
      {children}
      {loading && <span className="btn-spin" aria-hidden />}
    </button>
  );
});

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> {
  label: string;
  size?: ButtonSize;
  /** Toggle state: tinted background, same size. */
  pressed?: boolean;
  children: ReactNode;
}

/** Borderless icon control. Quiet until hover; `pressed` is a tint only. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton({ label, size = "md", pressed, className, children, type = "button", ...rest }, ref) {
  return (
    <Tooltip text={label}>
    <button ref={ref} type={type} className={`btn btn-ghost btn-icon btn-${size}${className ? ` ${className}` : ""}`} aria-label={label} aria-pressed={pressed} data-pressed={pressed || undefined} {...rest}>
      {children}
    </button>
    </Tooltip>
  );
});
