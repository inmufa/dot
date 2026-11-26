/** Live status text: a brightness wave runs through the letters, left to right. */
export function Shine({ text, className }: { text: string; className?: string }) {
  return (
    <span className={`shine${className ? ` ${className}` : ""}`}>
      <span className="sr-only">{text}</span>
      <span aria-hidden>
        {[...text].map((c, i) => (
          <span key={i} className="shine-ch" style={{ animationDelay: `${i * 70}ms` }}>{c === " " ? " " : c}</span>
        ))}
      </span>
    </span>
  );
}
