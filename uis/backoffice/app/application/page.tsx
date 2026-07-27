import { ApplicationForm } from "@/components/ApplicationForm";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";

export default function ApplicationPage() {
  return (
    <>
      <SiteHeader currentPage="application" />
      <main className="application-page" aria-label="Contenido principal del formulario de aplicacion">
        <section className="hero application-hero" aria-labelledby="application-title">
          <div className="grid-background" aria-hidden="true" />
          <div className="container">
            <div className="application-intro">
              <p className="pill">Aplicacion comercial</p>
              <h1 id="application-title">Cuentanos tu reto y te proponemos un plan con IA en 24h habiles.</h1>
              <p>
                Este formulario nos ayuda a entender tu contexto para disenar una propuesta enfocada en seleccion,
                ventas, RRHH, formacion o soporte.
              </p>
            </div>
            <ApplicationForm />
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
