import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Screen-Aware AI Tutor",
  description: "Privacy-first screen-aware tutoring dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <a className="brand" href="/">
            Screen-Aware AI Tutor
          </a>
          <span className="badge">Gemini 1.5 Flash · captures never stored</span>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
