import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { THEME_INIT_SCRIPT } from "@/components/ThemeToggle";

export const metadata = {
  title: "CreditCast · Risk Cockpit",
  description: "Bank-grade credit-risk modeling, validation, and monitoring.",
};

export default function RootLayout({ children }) {
  return (
    // suppressHydrationWarning: data-theme is set before React loads (below)
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before first paint, so there's no flash. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <div className="shell">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
