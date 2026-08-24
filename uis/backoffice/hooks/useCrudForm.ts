import { FormEvent, useState } from 'react';

export interface UseCrudFormOptions<TForm, TEntity extends { id: number }> {
  initialForm: TForm;
  createFn: (data: TForm) => Promise<TEntity>;
  updateFn: (id: number, data: TForm) => Promise<TEntity>;
  deleteFn: (id: number) => Promise<void>;
  loadData: () => Promise<void>;
  validateForm: (form: TForm) => string;
  mapEntityToForm: (entity: TEntity) => TForm;
  entityName?: string;
}

export function useCrudForm<TForm, TEntity extends { id: number }>({
  initialForm,
  createFn,
  updateFn,
  deleteFn,
  loadData,
  validateForm,
  mapEntityToForm,
  entityName = 'registro',
}: UseCrudFormOptions<TForm, TEntity>) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<TForm>(initialForm);

  function resetForm() {
    setEditingId(null);
    setForm(initialForm);
    setFormError('');
  }

  function onEdit(entity: TEntity) {
    setEditingId(entity.id);
    setFormError('');
    setForm(mapEntityToForm(entity));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError('');
    setError('');

    const validationError = validateForm(form);
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      if (editingId) {
        await updateFn(editingId, form);
      } else {
        await createFn(form);
      }
      resetForm();
      await loadData();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : `Error al guardar ${entityName}.`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(
    entity: TEntity,
    afterDelete?: () => void,
  ) {
    const entityLabel =
      (entity as unknown as Record<string, string>)?.name ||
      (entity as unknown as Record<string, string>)?.title ||
      entityName;

    if (!window.confirm(`¿Eliminar ${entityLabel}?`)) return;

    setError('');
    try {
      await deleteFn(entity.id);
      afterDelete?.();
      if (editingId === entity.id) resetForm();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : `Error al eliminar ${entityName}.`,
      );
    }
  }

  return {
    form,
    setForm,
    editingId,
    submitting,
    error,
    formError,
    resetForm,
    onEdit,
    onSubmit,
    onDelete,
  } as const;
}