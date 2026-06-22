const metrics = [
  { value: "-45%", copy: "de tiempo en tareas manuales de seleccion" },
  { value: "24h", copy: "objetivo de resolucion para soporte SLA" },
  { value: "Tiempo real", copy: "dashboard unificado para direccion ejecutiva" },
];

export function ImpactSection() {
  return (
    <section id="impacto" className="impact" aria-labelledby="impacto-title">
      <div className="container">
        <h2 id="impacto-title">Impacto medible</h2>
        <div className="impact-grid">
          {metrics.map((metric) => (
            <article key={metric.value} className="impact-card">
              <p className="metric-value">{metric.value}</p>
              <p>{metric.copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
