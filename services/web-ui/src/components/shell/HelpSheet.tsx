"use client";
import { useState } from "react";
import { Input, Kbd, Sheet } from "@/components/ui";
import { GROUP_LABEL, GROUP_ORDER } from "@/lib/commands/registry";
import { useApp } from "@/lib/state/app";
import "./help.css";

/** Each shortcut is a list of alternatives; each alternative is a chord of keys. */
const KEYS: { keys: string[][]; text: string }[] = [
  { keys: [["Ctrl", "K"]], text: "Search chats, commands, panels" },
  { keys: [["Ctrl", "Shift", "E"]], text: "Effort level" },
  { keys: [["Enter"], ["Shift", "Enter"]], text: "Send, new line" },
  { keys: [["Esc"]], text: "Stop the running turn, close a panel" },
  { keys: [["a"], ["s"], ["r"]], text: "Allow once, allow for session, reject" },
  { keys: [["/"]], text: "Open commands in the composer" },
  { keys: [["Space"]], text: "Dictate, when the composer is empty" },
];

/** Shortcut and command index: left column names the thing, right column says what it does. */
export function HelpSheet() {
  const { ui, commands } = useApp();
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const keys = KEYS.filter((k) => !needle || k.text.toLowerCase().includes(needle) || k.keys.some((c) => c.join(" ").toLowerCase().includes(needle)));
  return (
    <Sheet open={ui.overlay === "help"} onClose={ui.closeOverlay} title="Commands and shortcuts">
      <div className="hp-find"><Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter" aria-label="Filter shortcuts and commands" /></div>
      {keys.length > 0 && (
        <section className="hp-group">
          <p className="hp-label rec">keys <span>{keys.length}</span></p>
          <dl className="hp-list">
            {keys.map((k) => (
              <div key={k.text} className="hp-row">
                <dt>
                  {k.keys.map((chord, i) => (
                    <span key={i} className="hp-chord">
                      {i > 0 && <span className="hp-or" aria-hidden>/</span>}
                      {chord.map((c) => <Kbd key={c}>{c}</Kbd>)}
                    </span>
                  ))}
                </dt>
                <dd>{k.text}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {GROUP_ORDER.map((g) => {
        const list = commands.filter((c) => c.group === g && (!needle || c.name.toLowerCase().includes(needle) || c.description.toLowerCase().includes(needle)));
        return list.length ? (
          <section key={g} className="hp-group">
            <p className="hp-label rec">{GROUP_LABEL[g].toLowerCase()} <span>{list.length}</span></p>
            <dl className="hp-list">
              {list.map((c) => (
                <div key={c.name} className="hp-row">
                  <dt><code title={`/${c.name}${c.args ? ` ${c.args}` : ""}`}>/{c.name}{c.args ? ` ${c.args}` : ""}</code></dt>
                  <dd>{c.description}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null;
      })}
      {needle && keys.length === 0 && !commands.some((c) => c.name.toLowerCase().includes(needle) || c.description.toLowerCase().includes(needle)) && <p className="hp-none">Nothing matches that.</p>}
    </Sheet>
  );
}
