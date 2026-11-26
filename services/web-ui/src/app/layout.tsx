import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource-variable/onest";
import { ToastProvider } from "@/components/ui";
import "@/styles/brand.css";
import "@/styles/palettes.css";
import "@/styles/palettes-code.css";
import "@/styles/tokens.css";
import "@/styles/motion.css";
import "@/styles/base.css";
import "@/styles/ui.css";
import "@/components/ui/styles";
import "@/styles/shell.css";
import "@/styles/chat.css";
import "@/styles/approval.css";
import "@/styles/panels.css";
import "@/styles/features.css";
import "@/styles/layout.css";

export const metadata: Metadata = {
  title: "Dot",
  description: "Web cockpit for your local Dot agent.",
  // ?v= busts the browser favicon cache; bump it when the icons change
  icons: { icon: [{ url: "/icon.svg?v=2", type: "image/svg+xml" }, { url: "/favicon-32.png?v=2", sizes: "32x32" }], apple: "/apple-touch-icon.png?v=2" },
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
const THEME_BOOT = `try{var s=JSON.parse(localStorage.getItem("dot.settings")||"{}");if(s.theme==="light"||s.theme==="dark")document.documentElement.setAttribute("data-theme",s.theme);if(/^(clay|ink|plum|sand|mono)$/.test(s.palette))document.documentElement.setAttribute("data-palette",s.palette);if(s.density==="compact")document.documentElement.setAttribute("data-density","compact")}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body><ToastProvider>{children}</ToastProvider></body>
    </html>
  );
}
