"use client";
import { Archive, Brain, Copy, FolderOpen, MoreHorizontal, Pencil, Pin, Plus, Search, Send, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Avatar, Badge, Bullet, Entry, Button, ListRow, Progress, useToast, Card, Checkbox, Chip, Dialog, DropdownMenu, Field, IconButton, Input, Kbd, Menu, MenuItem, MenuLabel, MenuSeparator, Radio, Section, Segmented, Select, Sheet, Skeleton, StateBox, StateDot, Switch, Tabs, Textarea } from "@/components/ui";
import { KitSwitch, Palette } from "./Palette";
import "./kit.css";

function Row({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="kit-row">
      <h4>{title}</h4>
      <div className="kit-cells">{children}</div>
    </div>
  );
}

/** ?theme=light|dark forces the scheme (screenshots). */
export function Kit() {
  const [seg, setSeg] = useState("auto");
  const [tab, setTab] = useState("files");
  const [dlg, setDlg] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [menu, setMenu] = useState(false);
  const [pressed, setPressed] = useState(true);
  const toast = useToast();
  const [sel, setSel] = useState(1);
  const anchor = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    document.body.style.overflow = "auto";
    document.documentElement.style.height = "auto";
  }, []);
  return (
    <main className="kit">
      <h1>Dot UI kit</h1>
      <KitSwitch />
      <Row title="Palette (resolved live, contrast computed)"><Palette /></Row>
      <Row title="Button variants">
        <Button variant="solid">Solid</Button>
        <Button>Soft</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button variant="solid" icon={<Plus size={16} />}>With icon</Button>
        <Button disabled>Disabled</Button>
        <Button variant="solid" loading>Loading</Button>
      </Row>
      <Row title="Button sizes">
        <Button size="sm">Small</Button>
        <Button>Medium</Button>
        <Button size="lg" variant="solid">Large</Button>
      </Row>
      <Row title="Icon buttons (no border)">
        <IconButton label="Search"><Search size={18} /></IconButton>
        <IconButton label="Pressed" pressed={pressed} onClick={() => setPressed((p) => !p)}><Brain size={18} /></IconButton>
        <IconButton label="Small" size="sm"><Pencil size={16} /></IconButton>
        <IconButton label="Disabled" disabled><Trash2 size={18} /></IconButton>
        <IconButton label="Tooltip on hover or focus"><Copy size={18} /></IconButton>
        <IconButton label="Send" className="btn-primary"><Send size={18} /></IconButton>
      </Row>
      <Row title="Menu (dropdown, flips, arrows, Esc)">
        <DropdownMenu trigger={(p) => <IconButton label="Actions" {...p}><MoreHorizontal size={18} /></IconButton>} align="end">
          <MenuItem icon={<Pencil size={16} />}>Rename</MenuItem>
          <MenuItem icon={<Pin size={16} />} hint="P">Pin</MenuItem>
          <MenuItem icon={<Archive size={16} />}>Archive</MenuItem>
          <MenuSeparator />
          <MenuItem icon={<Trash2 size={16} />} danger>Delete</MenuItem>
        </DropdownMenu>
        <Button ref={anchor} onClick={() => setMenu((o) => !o)} aria-haspopup="menu" aria-expanded={menu}>Model</Button>
        <Menu open={menu} onClose={() => setMenu(false)} anchorRef={anchor}>
          <MenuLabel>Model</MenuLabel>
          <MenuItem selected onSelect={() => setMenu(false)}>Sonnet</MenuItem>
          <MenuItem selected={false} onSelect={() => setMenu(false)}>Opus</MenuItem>
          <MenuItem disabled>Haiku (unavailable)</MenuItem>
        </Menu>
        <DropdownMenu trigger={(p) => <Button variant="ghost" {...p}>Opens up</Button>} side="top">
          <MenuItem icon={<FolderOpen size={16} />}>Projects</MenuItem>
          <MenuItem>Settings</MenuItem>
        </DropdownMenu>
      </Row>
      <Row title="Tabs">
        <div style={{ width: "min(26rem,100%)" }}>
          <Tabs label="Canvas" value={tab} onChange={setTab} tabs={[{ id: "files", label: "Files", count: 4 }, { id: "diff", label: "Changes" }, { id: "preview", label: "Preview" }]} />
        </div>
      </Row>
      <Row title="Chip and Badge">
        <Chip icon={<Brain size={14} />} color="var(--mode-plan)">Plan</Chip>
        <Chip selected color="var(--mode-auto)" icon={<Brain size={14} />}>Auto</Chip>
        <Chip>Research</Chip>
        <Badge>Neutral</Badge>
        <Badge tone="accent">Accent</Badge>
        <Badge tone="ok">Allowed</Badge>
        <Badge tone="warn">Ask</Badge>
        <Badge tone="bad">Denied</Badge>
        <Badge tone="info">Info</Badge>
      </Row>
      <Row title="Fields">
        <div className="kit-fields">
          <Field label="Name" help="Shown in the sidebar.">{(p) => <Input placeholder="Untitled chat" {...p} />}</Field>
          <Field label="Error" error="Name is required.">{(p) => <Input defaultValue="" {...p} />}</Field>
          <Field label="Disabled">{(p) => <Input disabled defaultValue="Locked" {...p} />}</Field>
          <Field label="Notes">{(p) => <Textarea placeholder="Anything else" {...p} />}</Field>
          <Field label="Theme">{(p) => <Select {...p}><option>System</option><option>Light</option><option>Dark</option></Select>}</Field>
        </div>
      </Row>
      <Row title="Switch, Checkbox, Radio">
        <Switch defaultChecked>Notifications</Switch>
        <Switch>Off</Switch>
        <Switch disabled>Disabled</Switch>
        <Checkbox defaultChecked>Checked</Checkbox>
        <Checkbox>Unchecked</Checkbox>
        <Checkbox description="Helper text under the label">With description</Checkbox>
        <Radio name="r" defaultChecked>One</Radio>
        <Radio name="r">Two</Radio>
      </Row>
      <Row title="Segmented">
        <Segmented label="Mode" value={seg} onChange={setSeg} options={[{ value: "ask", label: "Ask" }, { value: "auto", label: "Auto" }, { value: "plan", label: "Plan" }]} />
        <Segmented label="Size" size="sm" value={seg} onChange={setSeg} options={[{ value: "ask", label: "Ask" }, { value: "auto", label: "Auto" }]} />
      </Row>
      <Row title="Card and Section">
        <Card tone="raised">Raised</Card>
        <Card tone="flat">Flat</Card>
        <Card tone="sunken">Sunken</Card>
        <Card tone="accent">Accent</Card>
        <div style={{ width: "100%" }}><Section title="Section title" hint="One line of help." action={<Button size="sm" variant="ghost">Edit</Button>}><Card tone="sunken">Content</Card></Section></div>
      </Row>
      <Row title="Kbd, StateDot">
        <span><Kbd>Ctrl</Kbd> <Kbd>K</Kbd></span>
        <StateDot state="idle" /><StateDot state="thinking" /><StateDot state="waiting" />
      </Row>
      <Row title="Skeleton and StateBox">
        <div style={{ width: "min(20rem,100%)", display: "grid", gap: 10 }}><Skeleton width="80%" /><Skeleton width="55%" /></div>
        <StateBox title="Nothing here yet" action={<Button size="sm">Create</Button>}>Items you add show up in this list.</StateBox>
      </Row>
      <Row title="Type scale (Onest, IBM Plex Mono)">
        <div className="kit-type">
          <p style={{ fontSize: "var(--fs-hero)", letterSpacing: "var(--ls-hero)", fontWeight: 600, lineHeight: "var(--lh-tight)" }}>Ready to dig in, Қобилжон? Oʻzbek gʻoyasi</p>
          <p className="title">Section title 18/600 Привет, мир</p>
          <p style={{ fontSize: "var(--fs-prose)", lineHeight: "var(--lh-prose)", maxWidth: "var(--prose)" }}>Prose 16/1.62. The agent edited three files, ran the tests and found nothing to fix. Ғ Қ Ў Ҳ ғ қ ў ҳ, oʻ gʻ, 0123456789.</p>
          <p style={{ fontSize: "var(--fs-ui)" }}>UI 15 regular, <b style={{ fontWeight: 500 }}>500 for labels</b>, <b>600 for emphasis</b></p>
          <p style={{ fontSize: "var(--fs-md)" }}>Control 14. <span className="meta">Meta 12, tabular 1,234.56 / 0O 1lI</span></p>
          <pre style={{ fontSize: "var(--fs-code)", lineHeight: "var(--lh-code)" }}><code>{"def add(a: int, b: int) -> int:  # → ≤ ≥ ×\n    return a + b  # Қ ғ oʻ"}</code></pre>
        </div>
      </Row>
      <Row title="Code highlight tokens">
        <pre className="kit-code"><code><span style={{ color: "var(--sh-token-keyword)" }}>def</span> <span style={{ color: "var(--sh-token-function)" }}>add</span>(a, b):{"\n"}  <span style={{ color: "var(--sh-token-comment)" }}># sum two numbers</span>{"\n"}  <span style={{ color: "var(--sh-token-keyword)" }}>return</span> a + b + <span style={{ color: "var(--sh-token-number)" }}>42</span>  <span style={{ color: "var(--sh-token-string)" }}>"ok"</span> <span style={{ color: "var(--sh-token-constant)" }}>None</span></code></pre>
        <div className="kit-chart">{[1, 2, 3, 4, 5, 6].map((n) => <span key={n} style={{ background: `var(--chart-${n})`, height: `${20 + n * 7}px` }} />)}</div>
      </Row>
      <Row title="List row (hover, selected, focus, actions slot)">
        <div className="kit-list">
          {["Refactor auth middleware", "Почему падает тест", "Oʻzbekcha interfeys tarjimasi"].map((t, i) => (
            <ListRow key={t} title={t} meta={i === 0 ? "2 min ago" : undefined} lead={i === 1 ? <StateDot state="waiting" /> : undefined} selected={sel === i} onSelect={() => setSel(i)} actions={<IconButton label={`${t} menu`} size="sm"><MoreHorizontal size={16} /></IconButton>} />
          ))}
        </div>
      </Row>
      <Row title="Character: logbook entries, bullets, index rows, dot progress, empty grid">
        <div className="kit-log">
          <Entry time="14:02" i={0}><p className="rec">you</p><p><b>Refactor the auth middleware</b></p></Entry>
          <Entry time="14:02" i={1} state="thinking"><p>Reading <span className="rec">src/auth/middleware.py</span> and its tests.</p></Entry>
          <Entry time="14:03" i={2}><p className="rec">step 3 · edit · 2 files</p><p>Done. The middleware takes a <code>TokenVerifier</code>.</p></Entry>
        </div>
        <div className="kit-list">
          <ListRow leader time="14:02" title="Refactor auth middleware" selected={sel === 0} onSelect={() => setSel(0)} />
          <ListRow leader time="Mon" title="Почему падает тест test_retry" lead={<Bullet size="s" tone="faint" />} selected={sel === 1} onSelect={() => setSel(1)} />
          <ListRow leader time="Nov 18" title="Oʻzbekcha interfeys tarjimasi" selected={sel === 2} onSelect={() => setSel(2)} />
        </div>
        <div style={{ width: "16rem", display: "grid", gap: 14 }}><Progress label="Index" value={0.4} /><Progress label="Waiting" /><Progress label="Done" value={1} tone="ok" /></div>
        <StateBox grid title="Nothing logged yet.">Ask Dot for something and it shows up here.</StateBox>
        <span className="rec">12:04 · 0.4s · 1,234 tok · src/a.py</span>
      </Row>
      <Row title="Toast, Progress, Avatar">
        <Button onClick={() => toast({ title: "Saved", description: "Settings applied.", tone: "ok" })}>Toast ok</Button>
        <Button onClick={() => toast({ title: "Chat archived", tone: "neutral", action: { label: "Undo", onClick: () => {} } })}>Toast with undo</Button>
        <Button onClick={() => toast({ title: "Could not reach the model", tone: "bad" })}>Toast error</Button>
        <div style={{ width: "12rem", display: "grid", gap: 10 }}><Progress label="Download" value={0.62} /><Progress label="Working" /></div>
        <Avatar name="Dot" /><Avatar name="Қобил Ғаниев" /><Avatar name="Anna K" size={36} />
      </Row>
      <Row title="Dialog and Sheet">
        <Button onClick={() => setDlg(true)}>Confirm dialog</Button>
        <Button onClick={() => setSheet(true)}>Side sheet</Button>
      </Row>
      <Dialog open={dlg} onClose={() => setDlg(false)} title="Delete chat?" confirmLabel="Delete" danger onConfirm={() => setDlg(false)}>This removes the chat and its files. It cannot be undone.</Dialog>
      <Sheet open={sheet} onClose={() => setSheet(false)} title="Settings"><Switch defaultChecked>Compact density</Switch></Sheet>
    </main>
  );
}
