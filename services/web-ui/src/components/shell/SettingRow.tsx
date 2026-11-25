import { useId, type ReactNode } from "react";

/** A settings section: heading and optional intro above one grouped list of rows. */
export function SettingGroup({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <section className="st-sec" aria-labelledby={id}>
      <header className="st-sec-head">
        <h3 id={id}>{title}</h3>
        {intro && <p className="st-sec-intro">{intro}</p>}
      </header>
      <div className="st-group">{children}</div>
    </section>
  );
}

interface RowProps {
  label: ReactNode;
  hint?: ReactNode;
  /** id of the control: the label text clicks/focuses it, the hint gets `${id}-hint` for aria-describedby. */
  htmlFor?: string;
  /** "inline" keeps the control on the right even on phones (switches); "block" puts it under the text everywhere. */
  layout?: "split" | "inline" | "block";
  children?: ReactNode;
}

/** One setting: label and hint left, control right on wide sheets; stacked on narrow ones. */
export function SettingRow({ label, hint, htmlFor, layout = "split", children }: RowProps) {
  const Label = htmlFor ? "label" : "span";
  return (
    <div className="st-row" data-layout={layout}>
      <div className="st-text">
        <Label className="st-label" htmlFor={htmlFor}>{label}</Label>
        {hint && <span className="st-hint" id={htmlFor ? `${htmlFor}-hint` : undefined}>{hint}</span>}
      </div>
      {children && <div className="st-ctl">{children}</div>}
    </div>
  );
}
