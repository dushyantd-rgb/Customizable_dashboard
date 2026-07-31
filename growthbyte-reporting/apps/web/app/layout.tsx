import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  description: "Standalone foundation for verified client reporting.",
  title: "GrowthByte Reporting Platform",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <header className="border-b border-growthbyte-black bg-growthbyte-white">
          <nav
            aria-label="Primary navigation"
            className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5"
          >
            <Link className="font-semibold tracking-tight" href="/">
              GrowthByte Reporting
            </Link>
            <Link
              className="border border-growthbyte-black px-3 py-2 text-sm font-medium hover:bg-growthbyte-black hover:text-growthbyte-white"
              href="/health"
            >
              Health
            </Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
