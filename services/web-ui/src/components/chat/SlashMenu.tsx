import type { SlashItem } from "@/lib/slash";

interface Props {
  id: string;
  items: SlashItem[];
  active: number;
  onPick: (i: SlashItem) => void;
  onHover: (i: number) => void;
}

export function SlashMenu({ id, items, active, onPick, onHover }: Props) {
  if (!items.length) {
    return (
      <div className="slash" id={id} role="listbox" aria-label="Commands">
        <p className="muted slash-empty">No command matches. Enter sends the text as a message.</p>
      </div>
    );
  }
  return (
    <ul className="slash" id={id} role="listbox" aria-label="Commands">
      {items.map((it, i) => (
        <li
          key={`${it.kind}-${it.name}`}
          id={`${id}-${i}`}
          role="option"
          aria-selected={i === active}
          aria-disabled={!it.available}
          data-active={i === active}
          onMouseEnter={() => onHover(i)}
          onMouseDown={(e) => {
            e.preventDefault();
            if (it.available) onPick(it);
          }}
        >
          <span className="slash-name">/{it.name}</span>
          <span className="slash-hint">{it.available ? it.hint : `Unavailable. ${it.hint}`}</span>
          <span className="slash-kind">{it.kind}</span>
        </li>
      ))}
    </ul>
  );
}
