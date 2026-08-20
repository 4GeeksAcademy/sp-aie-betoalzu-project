import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Outfit } from "next/font/google";
import Providers from "../components/Providers";
import NavBar from "../components/NavBar";
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
      <body className="min-h-full bg-surface text-slate-900" suppressHydrationWarning>
        <Providers>
          <div className="relative min-h-screen overflow-x-clip">
            <div className="pointer-events-none absolute inset-0 bg-grid" aria-hidden="true"></div>
            <NavBar />
            <div className="relative">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
