export type Palette = "sage" | "clay" | "ink" | "plum" | "sand" | "mono";
export const PALETTES: { id: Palette; label: string }[] = [
  { id: "sage", label: "Sage" },
  { id: "clay", label: "Clay" },
  { id: "ink", label: "Ink" },
  { id: "plum", label: "Plum" },
  { id: "sand", label: "Sand" },
  { id: "mono", label: "Mono" },
];
export const isPalette = (v: unknown): v is Palette => PALETTES.some((p) => p.id === v);
