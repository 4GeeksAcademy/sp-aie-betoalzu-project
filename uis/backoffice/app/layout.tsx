import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nexova Solutions | Talento, Formacion y Soporte con IA",
  description:
    "Nexova Solutions: consultora de talento con soluciones de seleccion, formacion y soporte escalable impulsadas por IA.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
