import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The One Lotto - Japan Loto 6 Results",
  description: "Latest Japan Loto 6 draw results and history",
};

const NAV_LINKS = [
  { href: "/",                    label: "Latest" },
  { href: "/predictions",         label: "Predictions" },
  { href: "/history",             label: "History" },
  { href: "/numbers",             label: "Numbers" },
  { href: "/backtest.html",       label: "Backtest" },
  { href: "/combo_evo.html",      label: "Combo Evo" },
  { href: "/special.html",        label: "Special" },
  { href: "/consecutive.html",    label: "Consecutive" },
  { href: "/position.html",       label: "Position" },
  { href: "/position.html#pos1pred", label: "Pos-1 Predict" },
  { href: "/overdue.html",        label: "Overdue" },
  { href: "/miss_analysis.html",  label: "Miss Analysis" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-950 text-gray-100" style={{ paddingTop: "52px" }}>
        {/* Fixed top nav */}
        <header style={{
          position: "fixed", top: 0, left: 0, right: 0, height: "52px",
          background: "#0a0f1e", borderBottom: "1px solid #1e293b",
          display: "flex", alignItems: "center", padding: "0 16px",
          zIndex: 9999, boxShadow: "0 2px 12px rgba(0,0,0,0.5)",
        }}>
          <a href="/" style={{
            fontWeight: 800, fontSize: "1rem", color: "#f1f5f9",
            textDecoration: "none", whiteSpace: "nowrap", marginRight: "16px", flexShrink: 0,
          }}>
            🎱 TheOneLotto
          </a>
          <nav style={{
            display: "flex", gap: "2px", overflowX: "auto",
            scrollbarWidth: "none", msOverflowStyle: "none",
          }}>
            {NAV_LINKS.map(({ href, label }) => (
              <a key={href} href={href} style={{
                color: "#94a3b8", textDecoration: "none", fontSize: ".78rem",
                padding: "5px 10px", borderRadius: "6px", whiteSpace: "nowrap",
                transition: "color .15s, background .15s",
              }}
              onMouseEnter={e => { (e.target as HTMLElement).style.color = "#f1f5f9"; (e.target as HTMLElement).style.background = "#1e293b"; }}
              onMouseLeave={e => { (e.target as HTMLElement).style.color = "#94a3b8"; (e.target as HTMLElement).style.background = "transparent"; }}
              >
                {label}
              </a>
            ))}
          </nav>
        </header>

        <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
        <footer className="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-500">
          Data sourced from Mizuho Bank · Japan Loto 6 · Not affiliated with Mizuho or JORA
        </footer>
      </body>
    </html>
  );
}




