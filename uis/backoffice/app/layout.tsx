import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Outfit } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Nexova Backoffice",
  description: "Backoffice de Nexova con acceso a herramientas operativas",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} ${outfit.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-surface text-slate-900">
        <div className="relative min-h-screen overflow-x-clip">
          <div className="pointer-events-none absolute inset-0 bg-grid" aria-hidden="true"></div>

          <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/90 backdrop-blur">
            <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
              <Link href="/" className="flex items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand text-sm font-extrabold text-white">
                  NX
                </span>
                <span className="text-lg font-extrabold tracking-tight text-brand">Nexova Backoffice</span>
              </Link>

              <nav className="flex items-center gap-2 sm:gap-4" aria-label="Navegacion principal">
                <Link href="/" className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand">
                  Herramientas
                </Link>
                <Link
                  href="/talent-pipeline-tracker"
                  className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
                >
                  Talent Pipeline Tracker
                </Link>
                <Link
                  href="/incident-analyzer"
                  className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
                >
                  Analizador de Incidentes
                </Link>
                <Link
                  href="/talent-pipeline-tracker/Candidates/new"
                  className="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-dark"
                >
                  Registrar nueva
                </Link>
              </nav>
            </div>
          </header>

          <div className="relative">{children}</div>
        </div>
      </body>
    </html>
  );
}
