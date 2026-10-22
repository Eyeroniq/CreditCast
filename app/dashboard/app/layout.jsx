import "./globals.css";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import TopBar from "@/components/TopBar";
import ScrollReveal from "@/components/ScrollReveal";
import { THEME_INIT_SCRIPT } from "@/components/ThemeToggle";
import Tour from "@/components/Tour";

// Self-hosted at build time by next/font: no requests to Google from visitors.
const display = Space_Grotesk({ subsets: ["latin"], weight: ["500", "600", "700"],
  variable: "--font-display", display: "swap" });
const body = Inter({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "600"],
  variable: "--font-mono", display: "swap" });

export const metadata = {
  title: "CreditCast · Risk Cockpit",
  description: "Bank-grade credit-risk modeling, validation, and monitoring.",
};

export default function RootLayout({ children }) {
  return (
    // suppressHydrationWarning: data-theme is set before React loads (below)
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}
      suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before first paint, so there's no flash. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <div className="ambient" aria-hidden="true" />
        <TopBar />
        <main className="main">{children}</main>
        <ScrollReveal />
        <Tour />
      </body>
    </html>
  );
}
