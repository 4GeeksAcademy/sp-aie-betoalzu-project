import Link from "next/link";

export function HeroSection() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="grid-background" aria-hidden="true" />
      <div className="container hero-grid">
        <div>
          <p className="pill">AI Engineering para talento B2B</p>
          <h1 id="hero-title">Escalamos la gestion de talento con datos, automatizacion e inteligencia artificial.</h1>
          <p className="hero-copy">
            En Nexova Solutions unimos seleccion, formacion y soporte para que tus equipos crezcan mas rapido, con menos
            friccion y mejor rendimiento operativo.
          </p>
          <div className="hero-actions">
            <Link href="/application" className="btn btn-primary">
              Quiero aplicar
            </Link>
            <a href="#servicios" className="btn btn-secondary">
              Ver servicios
            </a>
          </div>
        </div>

        <figure className="hero-card" aria-label="Imagen principal de equipo colaborando">
          <img
            src="https://images.unsplash.com/photo-1521737604893-d14cc237f11d?q=80&w=1200&auto=format&fit=crop"
            alt="Equipo profesional colaborando frente a un panel de metricas"
          />
          <figcaption>Operaciones de talento conectadas en tiempo real.</figcaption>
        </figure>
      </div>
    </section>
  );
}
