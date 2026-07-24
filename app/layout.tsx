import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The One Lotto - Japan Loto 6 Results",
  description: "Latest Japan Loto 6 draw results and history",
};

const NAV_GROUPS = [
  {
    label: "Data",
    items: [
      { href: "/",         icon: "🏠", label: "Latest Draw" },
      { href: "/history",  icon: "📋", label: "History" },
      { href: "/numbers",  icon: "🔢", label: "Numbers" },
    ],
  },
  {
    label: "Predict",
    items: [
      { href: "/predictions",        icon: "🎯", label: "Predictions" },
      { href: "/backtest.html",      icon: "📊", label: "Backtest" },
      { href: "/combo_evo.html",     icon: "🧬", label: "Combo Evo" },
      { href: "/overdue.html",        icon: "⏳", label: "Overdue" },
      { href: "/miss_analysis.html",  icon: "❌", label: "Miss Analysis" },
      { href: "/state_machine.html",  icon: "🔄", label: "State Machine" },
    ],
  },
  {
    label: "Analyze",
    items: [
      { href: "/special.html",          icon: "⭐", label: "Special" },
      { href: "/consecutive.html",      icon: "🔗", label: "Consecutive" },
      { href: "/position.html",          icon: "📍", label: "Position Freq" },
      { href: "/position.html#pos1pred", icon: "🎯", label: "Pos-1 Predict" },
      { href: "/pos_predict.html",       icon: "📊", label: "Pos 1–6 Predict" },
    ],
  },
];

const navStyle: React.CSSProperties = {
  position: "fixed", top: 0, left: 0, right: 0, height: "52px",
  background: "#0a0f1e", borderBottom: "1px solid #1e293b",
  display: "flex", alignItems: "center", padding: "0 20px",
  zIndex: 9999, boxShadow: "0 2px 16px rgba(0,0,0,.6)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <style>{`
          .nav-group{position:relative}
          .nav-group-btn{display:flex;align-items:center;gap:5px;padding:7px 14px;border-radius:7px;
            cursor:pointer;font-size:.82rem;font-weight:600;color:#94a3b8;
            border:1px solid transparent;transition:.15s;white-space:nowrap;user-select:none}
          .nav-group:hover .nav-group-btn{color:#f1f5f9;background:#1e293b;border-color:#334155}
          .nav-arrow{font-size:.6rem;opacity:.6;transition:transform .2s}
          .nav-group:hover .nav-arrow{transform:rotate(180deg)}
          .nav-dropdown{display:none;position:absolute;top:calc(100% + 6px);left:0;
            background:#0d1526;border:1px solid #1e293b;border-radius:10px;
            min-width:170px;padding:6px;box-shadow:0 12px 32px rgba(0,0,0,.7);z-index:10000}
          .nav-group:hover .nav-dropdown{display:block}
          .nav-dropdown a{display:flex;align-items:center;gap:8px;padding:8px 12px;
            border-radius:6px;color:#94a3b8;text-decoration:none;font-size:.82rem;
            white-space:nowrap;transition:.12s}
          .nav-dropdown a:hover{color:#f1f5f9;background:#1e293b}
        `}</style>
      </head>
      <body className="min-h-screen bg-gray-950 text-gray-100" style={{ paddingTop: "52px" }}>
        <header style={navStyle}>
          <a href="/" style={{
            fontWeight: 800, fontSize: "1rem", color: "#f1f5f9",
            textDecoration: "none", whiteSpace: "nowrap", marginRight: "24px", flexShrink: 0,
          }}>
            🎱 The<span style={{ color: "#38bdf8" }}>One</span>Lotto
          </a>
          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
            {NAV_GROUPS.map(group => (
              <div key={group.label} className="nav-group">
                <div className="nav-group-btn">
                  {group.label} <span className="nav-arrow">▼</span>
                </div>
                <div className="nav-dropdown">
                  {group.items.map(item => (
                    <a key={item.href} href={item.href}>
                      {item.icon} {item.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </header>

        <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
        <footer className="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-500">
          Data sourced from Mizuho Bank · Japan Loto 6 · Not affiliated with Mizuho or JORA
        </footer>
      </body>
    </html>
  );
}




