import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "The One Lotto - Japan Loto 6 Results",
  description: "Latest Japan Loto 6 draw results and history",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-950 text-gray-100" style={{ paddingTop: "52px" }}>
        {/* Shared nav (single source of truth, same as every public/*.html page) --
            injects its own <style> + <nav> markup and wires up the mobile hamburger
            menu. afterInteractive (not beforeInteractive) so it runs after React
            hydration completes, avoiding any hydration mismatch from DOM it injects
            outside React's own tree. */}
        <Script src="/site-nav.js" strategy="afterInteractive" />

        <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
        <footer className="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-500">
          Data sourced from Mizuho Bank · Japan Loto 6 · Not affiliated with Mizuho or JORA
        </footer>
        <Analytics />
      </body>
    </html>
  );
}




