import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The One Lotto - Japan Loto 6 Results",
  description: "Latest Japan Loto 6 draw results and history",
};

type NavItem =
  | { type?: "link"; href: string; icon: string; label: string }
  | { type: "divider" }
  | { type: "label"; label: string };

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Data",
    items: [
      { href: "/",        icon: "🏠", label: "Latest Draw" },
      { href: "/history", icon: "📋", label: "History" },
      { href: "/numbers", icon: "🔢", label: "Numbers" },
    ],
  },
  {
    label: "Predict",
    items: [
      { type: "label", label: "Prediction Tools" },
      { href: "/predictions",    icon: "🎯", label: "Predictions" },
      { href: "/backtest.html",  icon: "📊", label: "Backtest" },
      { href: "/combo_evo.html", icon: "🧬", label: "Combo Evo" },
      { type: "divider" },
      { type: "label", label: "Strategy" },
      { href: "/overdue.html",         icon: "⏳", label: "Overdue" },
      { href: "/state_machine.html",   icon: "🔄", label: "State Machine" },
      { href: "/modular_cycle.html",   icon: "🔁", label: "Modular Cycle" },
      { href: "/next_relation.html",   icon: "🔗", label: "Next Relation" },
      { href: "/lstm_predict.html",    icon: "🧠", label: "LSTM Neural Net" },
      { type: "divider" },
      { type: "label", label: "N-Draw Avg" },
      { href: "/avg_hub.html",         icon: "⬡", label: "All N-Draw Avg (2–43)" },
      { type: "divider" },
      { type: "label", label: "N-Draw Avg Shift" },
      { href: "/avg_shift_hub.html",   icon: "⇄", label: "All N-Shift Avg (2–43)" },
      { type: "divider" },
      { type: "label", label: "Random Seed" },
      { href: "/random_seed_backtest.html", icon: "🎲", label: "Random Seed (1–2000)" },
      { href: "/k7_seed_coverage.html", icon: "📈", label: "K=7 Seed Coverage" },
      { href: "/k7_seed_hit_1000.html", icon: "🗺️", label: "K=7 Seed-Hit (1000 draws)" },
    ],
  },
  {
    label: "Xoshiro Research",
    items: [
      { type: "label", label: "Xoshiro256** Seed Scans" },
      { href: "/xoshiro_seed_backtest.html", icon: "🌀", label: "K=21, seeds 0–1,000" },
      { href: "/xoshiro_seed_scan_k33.html", icon: "🎯", label: "K=33, seeds 0–1,000,000" },
      { href: "/xoshiro_seed_scan_k38.html", icon: "🔷", label: "K=38, seeds 0–1,000,000" },
      { href: "/xoshiro_seed_scan_k35.html", icon: "🟣", label: "K=35, seeds ±1,623,160" },
      { href: "/xoshiro_seed_scan_k7.html", icon: "🔎", label: "K=7, seeds 0–10,000" },
      { type: "divider" },
      { type: "label", label: "Predictions" },
      { href: "/xoshiro_elim_2128.html", icon: "✂️", label: "Draw #2128 Elimination" },
      { href: "/xoshiro_elim_2129.html", icon: "✂️", label: "Draw #2129 Elimination" },
      { href: "/xoshiro_k38_5seed_intersection.html", icon: "✂️", label: "K=38 5-Seed Intersection Backtest" },
      { href: "/xoshiro_k35_5seed_intersection.html", icon: "✂️", label: "K=35 5-Seed Intersection Backtest" },
      { href: "/xoshiro_k38_x_modularcycle_k28_intersection.html", icon: "✂️", label: "Modular Cycle × K=38 Intersection" },
    ],
  },
  {
    label: "Analyze",
    items: [
      { type: "label", label: "Pattern Analysis" },
      { href: "/special.html",     icon: "⭐", label: "Special" },
      { href: "/consecutive.html", icon: "🔗", label: "Consecutive" },
      { type: "divider" },
      { type: "label", label: "Position" },
      { href: "/position.html",    icon: "📍", label: "Position Freq" },
      { href: "/pos_predict.html", icon: "📊", label: "Pos 1–6 Predict" },
    ],
  },
  {
    label: "Loto7",
    items: [
      { type: "label", label: "Loto 7 (7 from 37 + 2 bonus)" },
      { href: "/loto7",             icon: "🏠", label: "Latest Draw" },
      { href: "/loto7/history",     icon: "📋", label: "History" },
      { href: "/loto7/predictions", icon: "🎯", label: "Predictions" },
      { href: "/loto7_backtest.html", icon: "📊", label: "Backtest" },
    ],
  },
  {
    label: "MiniLoto",
    items: [
      { type: "label", label: "MiniLoto (5 from 31 + 1 bonus)" },
      { href: "/miniloto",             icon: "🏠", label: "Latest Draw" },
      { href: "/miniloto/history",     icon: "📋", label: "History" },
      { href: "/miniloto/predictions", icon: "🎯", label: "Predictions" },
      { href: "/miniloto_backtest.html", icon: "📊", label: "Backtest" },
      { href: "/miniloto_rl23_minus_all19.html", icon: "🧮", label: "RL K=23 minus All-16 K=19" },
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
          .nav-dd-label{font-size:.68rem;font-weight:700;color:#475569;padding:6px 12px 2px;
            text-transform:uppercase;letter-spacing:.06em}
          .nav-divider{height:1px;background:#1e293b;margin:4px 0}
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
                  {group.items.map((item, i) => {
                    if (item.type === "divider") return <div key={i} className="nav-divider" />;
                    if (item.type === "label") return <div key={i} className="nav-dd-label">{item.label}</div>;
                    return (
                      <a key={item.href} href={item.href}>
                        {item.icon} {item.label}
                      </a>
                    );
                  })}
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




