"use client";
import { useState } from 'react';
import { CandidateForm } from '../types/candidate';

type CandidateFormState = Omit<CandidateForm, 'experience_years' | 'status' | 'stage'> & {
  experience_years: number | '';
  status: CandidateForm['status'] | '';
  stage: CandidateForm['stage'] | '';
};

interface Props {
  initial?: Partial<CandidateForm>;
  onSubmit: (data: CandidateForm) => void;
  loading?: boolean;
  error?: string | null;
  success?: boolean;
}

export default function CandidateFormComponent({ initial = {}, onSubmit, loading, error, success }: Props) {
  const [form, setForm] = useState<CandidateFormState>({
    full_name: initial.full_name || '',
    email: initial.email || '',
    phone: initial.phone || '',
    position: initial.position || '',
    linkedin: initial.linkedin || '',
    cv_url: initial.cv_url || '',
    experience_years: initial.experience_years ?? '',
    status: initial.status || '',
    stage: initial.stage || '',
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: name === 'experience_years' ? (value === '' ? '' : Number(value)) : value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (form.experience_years === '' || form.status === '' || form.stage === '') return;

    onSubmit({
      ...form,
      experience_years: form.experience_years,
      status: form.status,
      stage: form.stage,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="full_name" className="text-sm font-semibold text-slate-700">Nombre completo <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="full_name"
            name="full_name"
            value={form.full_name}
            onChange={handleChange}
            required
            placeholder="Nombre y apellidos"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-semibold text-slate-700">Correo electronico <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            required
            placeholder="correo@ejemplo.com"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="phone" className="text-sm font-semibold text-slate-700">Telefono <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="phone"
            name="phone"
            value={form.phone}
            onChange={handleChange}
            required
            placeholder="+34 600 123 456"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="position" className="text-sm font-semibold text-slate-700">Puesto <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="position"
            name="position"
            value={form.position}
            onChange={handleChange}
            required
            placeholder="Ej: Frontend Developer"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="linkedin" className="text-sm font-semibold text-slate-700">Perfil de LinkedIn <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="linkedin"
            name="linkedin"
            value={form.linkedin}
            onChange={handleChange}
            required
            placeholder="https://linkedin.com/in/usuario"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="cv_url" className="text-sm font-semibold text-slate-700">Enlace al CV <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="cv_url"
            name="cv_url"
            value={form.cv_url}
            onChange={handleChange}
            required
            placeholder="https://.../cv.pdf"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1">
          <label htmlFor="experience_years" className="text-sm font-semibold text-slate-700">Anos de experiencia <span className="text-red-600" aria-hidden="true">*</span></label>
          <input
            id="experience_years"
            name="experience_years"
            type="number"
            min={0}
            value={form.experience_years}
            onChange={handleChange}
            required
            placeholder="Ej: 3"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="status" className="text-sm font-semibold text-slate-700">Estado <span className="text-red-600" aria-hidden="true">*</span></label>
          <select
            id="status"
            name="status"
            value={form.status}
            onChange={handleChange}
            required
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          >
            <option value="" disabled>Selecciona un estado</option>
            <option value="received">Recibida</option>
            <option value="in_progress">En proceso</option>
            <option value="selected">Seleccionada</option>
            <option value="discarded">Descartada</option>
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="stage" className="text-sm font-semibold text-slate-700">Etapa del proceso <span className="text-red-600" aria-hidden="true">*</span></label>
          <select
            id="stage"
            name="stage"
            value={form.stage}
            onChange={handleChange}
            required
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
          >
            <option value="" disabled>Selecciona una etapa</option>
            <option value="pending">Pendiente de revision</option>
            <option value="review">En revision</option>
            <option value="personal_interview">Entrevista personal</option>
            <option value="technical_interview">Entrevista tecnica</option>
            <option value="offer_presented">Oferta presentada</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          className="rounded-full bg-brand px-6 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
        >
          {loading ? 'Guardando...' : 'Guardar candidatura'}
        </button>
        {success && (
          <div className="rounded-full bg-emerald-100 px-4 py-2 text-sm font-semibold text-emerald-700">
            Enviado con exito.
          </div>
        )}
      </div>
      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</div>}
    </form>
  );
}
