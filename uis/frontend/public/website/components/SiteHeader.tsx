import Link from "next/link";

type SiteHeaderProps = {
  currentPage: "home" | "application";
};

export function SiteHeader({ currentPage }: SiteHeaderProps) {
  return (
    <header className="site-header" aria-label="Cabecera principal">
      <div className="container header-content">
        <Link href="/" className="brand" aria-label="Volver al inicio de Nexova Solutions">
          <img
            src="https://images.unsplash.com/photo-1560179707-f14e90ef3623?q=80&w=120&auto=format&fit=crop"
            alt="Logotipo de Nexova Solutions"
            className="brand-logo"
          />
          <span className="brand-text">Nexova Solutions</span>
        </Link>

        <nav aria-label="Navegacion principal" className="desktop-nav">
          <Link href="/#servicios">Servicios</Link>
          <Link href="/#impacto">Impacto</Link>
          <Link href="/#contacto">Contacto</Link>
          <Link
            href="/application"
            className={`btn btn-primary ${currentPage === "application" ? "is-current" : ""}`}
            aria-current={currentPage === "application" ? "page" : undefined}
          >
            Aplicar ahora
          </Link>
        </nav>

        <Link
          href="/application"
          className={`btn btn-primary mobile-only ${currentPage === "application" ? "is-current" : ""}`}
          aria-current={currentPage === "application" ? "page" : undefined}
        >
          Aplicar
        </Link>
      </div>
    </header>
  );
}
