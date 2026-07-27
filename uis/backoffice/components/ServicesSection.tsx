const services = [
  {
    title: "Seleccion Asistida",
    copy: "Scoring de CVs, ranking explicable y seguimiento automatico de candidatos.",
  },
  {
    title: "Ventas Inteligentes",
    copy: "Automatizacion de secuencias y alertas de oportunidades sin actividad.",
  },
  {
    title: "Formacion Corporativa",
    copy: "Catalogo online, recomendaciones por perfil y trazabilidad del aprendizaje.",
  },
  {
    title: "Soporte Externalizado",
    copy: "Chatbot de primera linea, base de conocimiento y panel de SLA en vivo.",
  },
];

export function ServicesSection() {
  return (
    <section id="servicios" className="services" aria-labelledby="servicios-title">
      <div className="container">
        <h2 id="servicios-title">Lo que hacemos</h2>
        <p className="section-copy">Soluciones modulares para seleccion, ventas, formacion y soporte empresarial.</p>

        <div className="services-grid" role="list" aria-label="Lista de servicios">
          {services.map((service) => (
            <article key={service.title} className="service-card" role="listitem">
              <h3>{service.title}</h3>
              <p>{service.copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
