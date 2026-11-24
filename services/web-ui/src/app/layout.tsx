import type { Metadata, Viewport } from "next";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/onest";
import "@/styles/brand.css";
import "@/styles/tokens.css";
import "@/styles/base.css";
import "@/styles/ui.css";
import "@/styles/shell.css";
import "@/styles/chat.css";
import "@/styles/approval.css";
import "@/styles/panels.css";
import "@/styles/features.css";

export const metadata: Metadata = {
  title: "Dot",
  description: "Web cockpit for your local Dot agent.",
  icons: { icon: [{ url: "/icon.svg", type: "image/svg+xml" }, { url: "/favicon-32.png", sizes: "32x32" }], apple: "/apple-touch-icon.png" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f0f8fc" },
    { media: "(prefers-color-scheme: dark)", color: "#090e11" },
  ],
};

// Runs before paint so the saved theme never flashes.
const THEME_BOOT = `try{var s=JSON.parse(localStorage.getItem("dot.settings")||"{}");if(s.theme==="light"||s.theme==="dark")document.documentElement.setAttribute("data-theme",s.theme)}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
