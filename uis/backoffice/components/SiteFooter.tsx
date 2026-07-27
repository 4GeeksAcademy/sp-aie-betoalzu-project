export function SiteFooter() {
  return (
    <footer id="contacto" className="site-footer" aria-label="Pie de pagina con informacion de contacto">
      <div className="container footer-grid">
        <div>
          <h2 className="footer-title">Nexova Solutions</h2>
          <p className="footer-text">Consultoria de talento, formacion y soporte B2B en Espana y Estados Unidos.</p>
        </div>

        <address className="footer-address" aria-label="Informacion de contacto de Nexova Solutions">
          <p>
            <strong>Tel:</strong> +34 960 000 120
          </p>
          <p>
            <strong>Email:</strong> contacto@nexovasolutions.com
          </p>
          <p>
            <strong>Direccion:</strong> Avenida de la Innovacion 45, Valencia, Espana
          </p>
        </address>
      </div>
    </footer>
  );
}
