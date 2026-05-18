"use client";
import { useState } from 'react';
import { CandidateForm } from '../types/candidate';

interface Props {
  initial?: Partial<CandidateForm>;
  onSubmit: (data: CandidateForm) => void;
  loading?: boolean;
  error?: string | null;
  success?: boolean;
}

export default function CandidateFormComponent({ initial = {}, onSubmit, loading, error, success }: Props) {
  const [form, setForm] = useState<CandidateForm>({
    full_name: initial.full_name || '',
    email: initial.email || '',
    phone: initial.phone || '',
    position: initial.position || '',
    linkedin: initial.linkedin || '',
    cv_url: initial.cv_url || '',
    experience_years: initial.experience_years || 0,
    status: initial.status || 'received',
    stage: initial.stage || 'pending',
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: name === 'experience_years' ? Number(value) : value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input name="full_name" value={form.full_name} onChange={handleChange} required placeholder="Nombre completo" className="border rounded px-3 py-2 w-full" />
      <input name="email" value={form.email} onChange={handleChange} required placeholder="Email" className="border rounded px-3 py-2 w-full" />
      <input name="phone" value={form.phone} onChange={handleChange} required placeholder="Teléfono" className="border rounded px-3 py-2 w-full" />
      <input name="position" value={form.position} onChange={handleChange} required placeholder="Puesto" className="border rounded px-3 py-2 w-full" />
      <input name="linkedin" value={form.linkedin} onChange={handleChange} required placeholder="LinkedIn" className="border rounded px-3 py-2 w-full" />
      <input name="cv_url" value={form.cv_url} onChange={handleChange} required placeholder="Enlace al CV" className="border rounded px-3 py-2 w-full" />
      <input name="experience_years" type="number" value={form.experience_years} onChange={handleChange} required placeholder="Años de experiencia" className="border rounded px-3 py-2 w-full" />
      <select name="status" value={form.status} onChange={handleChange} required className="border rounded px-3 py-2 w-full">
        <option value="received">Recibida</option>
        <option value="in_progress">En proceso</option>
        <option value="selected">Seleccionada</option>
        <option value="discarded">Descartada</option>
      </select>
      <select name="stage" value={form.stage} onChange={handleChange} required className="border rounded px-3 py-2 w-full">
        <option value="pending">Pendiente de revisión</option>
        <option value="review">En revisión</option>
        <option value="personal_interview">Entrevista personal</option>
        <option value="technical_interview">Entrevista técnica</option>
        <option value="offer_presented">Oferta presentada</option>
      </select>
      <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded" disabled={loading}>Enviar</button>
      {error && <div className="text-red-600">{error}</div>}
      {success && <div className="text-green-600">¡Enviado con éxito!</div>}
    </form>
  );
}
