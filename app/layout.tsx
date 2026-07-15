import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The One Lotto - Japan Loto 6 Results",
  description: "Latest Japan Loto 6 draw results and history",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 dark:bg-gray-950">
        <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-gray-900 dark:text-white">
              🎱 TheOneLotto
            </a>
            <nav className="flex gap-6 text-sm text-gray-600 dark:text-gray-400">
              <a href="/" className="hover:text-gray-900 dark:hover:text-white transition-colors">Latest</a>
              <a href="/predictions" className="hover:text-gray-900 dark:hover:text-white transition-colors">Predictions</a>
              <a href="/history" className="hover:text-gray-900 dark:hover:text-white transition-colors">History</a>
            </nav>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-4 py-8">{children}</main>
        <footer className="mt-16 border-t border-gray-200 dark:border-gray-800 py-6 text-center text-xs text-gray-400">
          Data sourced from Mizuho Bank · Japan Loto 6 · Not affiliated with Mizuho or JORA
        </footer>
      </body>
    </html>
  );
}
