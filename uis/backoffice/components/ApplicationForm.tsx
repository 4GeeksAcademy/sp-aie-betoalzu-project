"use client";

import { FormEvent, useMemo, useState } from "react";
import { ApplicationFormData, ApplicationFormErrors, initialFormData } from "@/types/application";

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const urlRegex = /^https?:\/\/.+/i;

function validate(data: ApplicationFormData): ApplicationFormErrors {
  const errors: ApplicationFormErrors = {};

  if (data.fullName.trim().length < 3) errors.fullName = "Ingresa un nombre valido (minimo 3 caracteres).";
  if (!emailRegex.test(data.workEmail.trim())) errors.workEmail = "Ingresa un email corporativo valido.";
  if (data.phone.trim().length < 7) errors.phone = "Ingresa un telefono valido.";
  if (data.companyName.trim().length < 2) errors.companyName = "Ingresa el nombre de la empresa.";
  if (data.companyWebsite && !urlRegex.test(data.companyWebsite.trim())) errors.companyWebsite = "Usa una URL valida que inicie con http:// o https://.";
  if (!data.industry) errors.industry = "Selecciona un sector.";
  if (!data.companySize) errors.companySize = "Selecciona el tamano de la empresa.";
  if (!data.services.length) errors.services = "Selecciona al menos un servicio.";
  if (!data.priorityArea) errors.priorityArea = "Selecciona un area prioritaria.";
  if (!data.budget) errors.budget = "Selecciona un rango de presupuesto.";
  if (!data.timeline) errors.timeline = "Selecciona un tiempo objetivo de inicio.";
  if (data.projectDetails.trim().length < 20) errors.projectDetails = "Describe el reto con al menos 20 caracteres.";
  if (!data.privacyConsent) errors.privacyConsent = "Debes aceptar el tratamiento de datos para enviar.";

  return errors;
}

export function ApplicationForm() {
  const [formData, setFormData] = useState<ApplicationFormData>(initialFormData);
  const [errors, setErrors] = useState<ApplicationFormErrors>({});
  const [submitted, setSubmitted] = useState(false);

  const hasErrors = useMemo(() => Object.keys(errors).length > 0, [errors]);

  const updateField = <K extends keyof ApplicationFormData>(field: K, value: ApplicationFormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validate(formData);
    setErrors(nextErrors);
    setSubmitted(Object.keys(nextErrors).length === 0);

    if (Object.keys(nextErrors).length === 0) {
      setFormData(initialFormData);
    }
  };

  const onReset = () => {
    setFormData(initialFormData);
    setErrors({});
    setSubmitted(false);
  };

  const toggleService = (service: string) => {
    setFormData((prev) => {
      const nextServices = prev.services.includes(service)
        ? prev.services.filter((item) => item !== service)
        : [...prev.services, service];

      return { ...prev, services: nextServices };
    });
  };

  return (
    <>
      {submitted && (
        <div className="success-box" role="status" aria-live="polite">
          Solicitud enviada con exito. Nuestro equipo te contactara en menos de 24 horas habiles.
        </div>
      )}

      <form className="application-form" onSubmit={onSubmit} onReset={onReset} noValidate>
        <fieldset>
          <legend>Datos de contacto</legend>
          <div className="field-grid two-col">
            <label>
              Nombre completo *
              <input value={formData.fullName} onChange={(e) => updateField("fullName", e.target.value)} />
              <span className="error">{errors.fullName}</span>
            </label>
            <label>
              Cargo
              <input value={formData.jobTitle} onChange={(e) => updateField("jobTitle", e.target.value)} />
              <span className="error">{errors.jobTitle}</span>
            </label>
          </div>

          <div className="field-grid two-col">
            <label>
              Email corporativo *
              <input type="email" value={formData.workEmail} onChange={(e) => updateField("workEmail", e.target.value)} />
              <span className="error">{errors.workEmail}</span>
            </label>
            <label>
              Telefono de contacto *
              <input value={formData.phone} onChange={(e) => updateField("phone", e.target.value)} />
              <span className="error">{errors.phone}</span>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Datos de empresa</legend>
          <div className="field-grid two-col">
            <label>
              Empresa *
              <input value={formData.companyName} onChange={(e) => updateField("companyName", e.target.value)} />
              <span className="error">{errors.companyName}</span>
            </label>
            <label>
              Sitio web
              <input value={formData.companyWebsite} onChange={(e) => updateField("companyWebsite", e.target.value)} placeholder="https://tuempresa.com" />
              <span className="error">{errors.companyWebsite}</span>
            </label>
          </div>

          <div className="field-grid two-col">
            <label>
              Sector *
              <select value={formData.industry} onChange={(e) => updateField("industry", e.target.value)}>
                <option value="">Selecciona un sector</option>
                <option value="tecnologia">Tecnologia</option>
                <option value="retail">Retail</option>
                <option value="finanzas">Servicios financieros</option>
                <option value="salud">Salud</option>
                <option value="otro">Otro</option>
              </select>
              <span className="error">{errors.industry}</span>
            </label>
            <label>
              Tamano de empresa *
              <select value={formData.companySize} onChange={(e) => updateField("companySize", e.target.value)}>
                <option value="">Selecciona rango</option>
                <option value="1-50">1-50 empleados</option>
                <option value="51-200">51-200 empleados</option>
                <option value="201-500">201-500 empleados</option>
                <option value="500+">500+ empleados</option>
              </select>
              <span className="error">{errors.companySize}</span>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Objetivo del proyecto</legend>

          <div>
            <p className="field-title">Servicio que necesitas *</p>
            <div className="check-grid two-col">
              {[
                ["seleccion", "Seleccion asistida por IA"],
                ["ventas", "Automatizacion de ventas"],
                ["rrhh", "Portal y agente de RRHH"],
                ["formacion", "Plataforma de formacion"],
                ["soporte", "Soporte externalizado con chatbot y RAG"],
              ].map(([value, label]) => (
                <label className="check-option" key={value}>
                  <input
                    type="checkbox"
                    checked={formData.services.includes(value)}
                    onChange={() => toggleService(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <span className="error">{errors.services}</span>
          </div>

          <div>
            <p className="field-title">Area prioritaria *</p>
            <div className="check-grid three-col">
              {[
                ["operaciones", "Operaciones"],
                ["ventas", "Ventas"],
                ["direccion", "Direccion ejecutiva"],
              ].map(([value, label]) => (
                <label className="check-option" key={value}>
                  <input
                    type="radio"
                    name="priorityArea"
                    checked={formData.priorityArea === value}
                    onChange={() => updateField("priorityArea", value)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <span className="error">{errors.priorityArea}</span>
          </div>

          <div className="field-grid two-col">
            <label>
              Rango de presupuesto mensual *
              <select value={formData.budget} onChange={(e) => updateField("budget", e.target.value)}>
                <option value="">Selecciona una opcion</option>
                <option value="2000-5000">2.000 EUR - 5.000 EUR</option>
                <option value="5000-12000">5.000 EUR - 12.000 EUR</option>
                <option value="12000-25000">12.000 EUR - 25.000 EUR</option>
                <option value="25000+">25.000 EUR+</option>
              </select>
              <span className="error">{errors.budget}</span>
            </label>

            <label>
              Tiempo objetivo de inicio *
              <select value={formData.timeline} onChange={(e) => updateField("timeline", e.target.value)}>
                <option value="">Selecciona una opcion</option>
                <option value="inmediato">Inmediato (0-30 dias)</option>
                <option value="1-2meses">1-2 meses</option>
                <option value="trimestre">Este trimestre</option>
                <option value="sin-fecha">Aun sin fecha</option>
              </select>
              <span className="error">{errors.timeline}</span>
            </label>
          </div>

          <label>
            Describe el reto principal *
            <textarea
              rows={5}
              value={formData.projectDetails}
              onChange={(e) => updateField("projectDetails", e.target.value)}
              placeholder="Ej. Necesitamos reducir el tiempo de contratacion en un 35% y mejorar la visibilidad del pipeline."
            />
            <span className="error">{errors.projectDetails}</span>
          </label>
        </fieldset>

        <fieldset>
          <legend>Privacidad y envio</legend>

          <label className="inline-check">
            <input
              type="checkbox"
              checked={formData.privacyConsent}
              onChange={(e) => updateField("privacyConsent", e.target.checked)}
            />
            Acepto el tratamiento de mis datos para recibir una propuesta comercial. *
          </label>
          <span className="error">{errors.privacyConsent}</span>

          <label className="inline-check">
            <input
              type="checkbox"
              checked={formData.newsletter}
              onChange={(e) => updateField("newsletter", e.target.checked)}
            />
            Quiero recibir novedades sobre automatizacion e IA aplicada a operaciones.
          </label>
        </fieldset>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary">
            Enviar solicitud
          </button>
          <button type="reset" className="btn btn-secondary">
            Limpiar formulario
          </button>
        </div>

        {hasErrors && <p className="form-note">Revisa los campos marcados antes de enviar.</p>}
      </form>
    </>
  );
}
