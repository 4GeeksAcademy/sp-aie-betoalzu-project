import type { Metadata } from "next";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource-variable/outfit";
import Providers from "../components/Providers";
import NavBar from "../components/NavBar";
import { themeInitScript } from "../lib/theme";
import "./globals.css";

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
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full bg-surface text-slate-900" suppressHydrationWarning>
        <Providers>
          <div className="relative min-h-screen overflow-x-clip">
            <NavBar />
            <div className="relative">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
