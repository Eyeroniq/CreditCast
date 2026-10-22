import "./globals.css";
import localFont from "next/font/local";
import TopBar from "@/components/TopBar";
import ScrollReveal from "@/components/ScrollReveal";
import { THEME_INIT_SCRIPT } from "@/components/ThemeToggle";
import Tour from "@/components/Tour";

// Fonts ship with the app (Fontsource variable builds, OFL), so neither the
// build nor visitors ever contact Google Fonts.
const display = localFont({ src:
    "../node_modules/@fontsource-variable/space-grotesk/files/space-grotesk-latin-wght-normal.woff2",
  weight: "300 700", variable: "--font-display", display: "swap" });
const body = localFont({ src:
    "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  weight: "100 900", variable: "--font-body", display: "swap" });
const mono = localFont({ src:
    "../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2",
  weight: "100 800", variable: "--font-mono", display: "swap" });

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
