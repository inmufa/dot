import type { HTMLAttributes, ReactNode } from "react";

type Tone = "flat" | "raised" | "sunken" | "accent";

/** Flat tone-based container. Hierarchy comes from the fill, never from an outline. */
export function Card({ tone = "raised", pad = true, className, ...rest }: HTMLAttributes<HTMLDivElement> & { tone?: Tone; pad?: boolean }) {
  return <div className={`card${className ? ` ${className}` : ""}`} data-tone={tone} data-pad={pad} {...rest} />;
}

interface SectionProps { title?: string; hint?: ReactNode; action?: ReactNode; children: ReactNode }

/** Titled block: heading in type weight, optional right action, content below. */
export function Section({ title, hint, action, children }: SectionProps) {
  return (
    <section className="sect">
      {(title || action) && (
        <header className="sect-head">
          <div>
            {title && <h3>{title}</h3>}
            {hint && <p className="sect-hint">{hint}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
