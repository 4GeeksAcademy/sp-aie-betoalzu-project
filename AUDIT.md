# Auditoría de Lógica Duplicada: Componentes Frontend

> **Fecha:** 2026-08-24
> **Alcance:** `uis/backoffice/` (Next.js + React) y `uis/website/` (HTML + Vanilla JS)
> **Propósito:** Identificar lógica duplicada extraíble a custom hooks (React) o funciones reutilizables (Vanilla JS).

---

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Frontend 1: Backoffice (Next.js / React)](#2-frontend-1-backoffice-nextjs-react)
   - [Caso A: Patrón CRUD compartido — IncidentsManagerClient vs SuppliersManagerClient](#21-caso-a-patrón-crud-compartido)
   - [Caso B: Carga inicial manual — no usa `useAsync`](#22-caso-b-carga-inicial-manual)
3. [Frontend 2: Website (HTML + Vanilla JS)](#3-frontend-2-website-html--vanilla-js)
   - [Caso A: Registro duplicado de event listeners](#31-caso-a-registro-duplicado-de-event-listeners)
   - [Caso B: Validación de grupos checkbox/radio](#32-caso-b-validación-de-grupos-checkboxradio)
4. [Impacto estimado del refactor](#4-impacto-estimado-del-refactor)

---

## 1. Resumen ejecutivo

Se analizaron los dos frontends del proyecto —el **backoffice** (React/Next.js) y el **website corporativo** (HTML vanilla)— buscando patrones de lógica duplicada que puedan encapsularse en **custom hooks** (React) o **funciones reutilizables** (Vanilla JS).

| Frontend | Casos detectados | Líneas duplicadas aprox. | Solución propuesta |
|---|---|---|---|
| Backoffice | Patrón CRUD en 2 componentes | ~80 líneas cada uno | Hook `useCrudForm` |
| Backoffice | Carga inicial sin `useAsync` | ~15 líneas cada uno | Hook `useAsync` (ya existe) |
| Website | Event listeners duplicados | ~12 líneas | Función `setupFieldValidation` |
| Website | Validación de grupos | ~15 líneas | Función `validateCheckboxGroup` |

---

## 2. Frontend 1: Backoffice (Next.js / React)

### 2.1. Caso A: Patrón CRUD compartido

#### Por qué elegí estos componentes

Los componentes **`IncidentsManagerClient`** y **`SuppliersManagerClient`** son los dos componentes de gestión de entidades más completos del backoffice. Ambos implementan un formulario que permite **crear, editar y eliminar** registros, con validación, estados de carga y manejo de errores. La estructura de sus funciones es prácticamente idéntica:

| Función | IncidentsManagerClient | SuppliersManagerClient |
|---|---|---|
| `resetForm()` | Resetea `editingId`, `form`, `formError` | Idéntica |
| `validateForm()` | Valida campos obligatorios | Idéntica en patrón |
| `onEdit(entity)` | Mapea entidad → formulario | Misma estructura |
| `onSubmit(event)` | Guarda (crea o actualiza), recarga | Misma estructura |
| `onDelete(entity)` | Confirma, elimina, actualiza estado local | Misma estructura |

**Estados manuales repetidos en ambos:**

```tsx
const [loading, setLoading] = useState(false);
const [submitting, setSubmitting] = useState(false);
const [error, setError] = useState('');
const [formError, setFormError] = useState('');
const [editingId, setEditingId] = useState<number | null>(null);
const [form, setForm] = useState<InputType>(INITIAL_FORM);
```

#### Cómo lo refactorizaría

Crearía un custom hook genérico `useCrudForm<TForm, TEntity>` que encapsule todo el ciclo de vida de un CRUD con formulario. El hook recibiría por parámetro:

- `initialForm`: valor inicial del formulario
- `createFn` / `updateFn` / `deleteFn`: funciones API a invocar
- `loadData`: función para recargar datos tras una operación
- `validateForm`: función de validación específica del formulario
- `mapEntityToForm`: transformación de entidad a valores del formulario

#### Implementación propuesta

**Archivo:** `uis/backoffice/hooks/useCrudForm.ts`

```tsx
import { FormEvent, useState } from 'react';

interface UseCrudFormOptions<TForm, TEntity extends { id: number }> {
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
        err instanceof Error ? err.message : `Error al guardar ${entityName}.`
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(
    entity: TEntity,
    afterDelete?: () => void
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
          : `Error al eliminar ${entityName}.`
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
  };
}
```

**Cómo quedaría en `IncidentsManagerClient.tsx` (simplificado):**

```tsx
const crud = useCrudForm({
  initialForm: INITIAL_FORM,
  createFn: createIncident,
  updateFn: (id, data) => updateIncident(id, data as IncidentInput),
  deleteFn: (id) => deleteIncident(id),
  loadData,
  validateForm: (form) => {
    if (!form.title.trim()) return 'El título es obligatorio.';
    return '';
  },
  mapEntityToForm: (incident) => ({
    title: incident.title,
    description: incident.description || '',
    category: incident.category,
    origin: incident.origin,
    branch: incident.branch,
    reported_by: incident.reported_by || '',
    assigned_to: incident.assigned_to || '',
  }),
  entityName: 'incidencia',
});

// El componente usa crud.form, crud.onSubmit, crud.onEdit, crud.onDelete...
```

**Cómo quedaría en `SuppliersManagerClient.tsx` (simplificado):**

```tsx
const crud = useCrudForm({
  initialForm: INITIAL_FORM,
  createFn: createSupplier,
  updateFn: (id, data) => updateSupplier(id, data as SupplierInput),
  deleteFn: (id) => deleteSupplier(id),
  loadData: loadSuppliers,
  validateForm: (form) => {
    if (!form.name.trim()) return 'El nombre es obligatorio.';
    if (form.categories.length === 0) return 'Selecciona al menos una categoría.';
    if (!Number.isFinite(form.monthly_rate) || form.monthly_rate <= 0)
      return 'La tarifa mensual debe ser mayor que 0.';
    return '';
  },
  mapEntityToForm: (supplier) => ({
    name: supplier.name,
    country: supplier.country,
    categories: supplier.categories,
    monthly_rate: supplier.monthly_rate,
    currency: supplier.currency,
    status: supplier.status,
    contract_renewal_date: supplier.contract_renewal_date,
    contact_email: supplier.contact_email,
    notes: supplier.notes,
  }),
  entityName: 'proveedor',
});
```

**Beneficio:** cada componente pierde entre 60 y 80 líneas de lógica CRUD repetitiva, quedando únicamente la configuración del hook (~15 líneas) y el JSX.

---

### 2.2. Caso B: Carga inicial manual

#### Por qué elegí estos componentes

El hook `useAsync` ya existe en `uis/backoffice/hooks/useAsync.ts`:

```tsx
export function useAsync<T>(asyncFn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    asyncFn()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, deps);

  return { data, loading, error };
}
```

Sin embargo, los componentes `IncidentsManagerClient` y `SuppliersManagerClient` **no lo usan** y en su lugar implementan la lógica de carga manualmente. Por ejemplo, en `IncidentsManagerClient`:

```tsx
async function loadData() {
  setLoading(true);      // ← boilerplate
  setError('');           // ← boilerplate
  try {
    const [incidentsData, summaryData] = await Promise.all([
      getIncidents({...}),
      getIncidentsSummary(),
    ]);
    setIncidents(incidentsData);
    setSummary(summaryData);
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Error al cargar incidencias.');
  } finally {
    setLoading(false);    // ← boilerplate
  }
}
```

#### Cómo lo refactorizaría

Reemplazar la función `loadData` y los estados manuales por `useAsync` para la carga inicial y añadir una función de recarga para cuando se necesite refrescar tras un CRUD.

**Implementación propuesta:**

```tsx
// En IncidentsManagerClient
const {
  data,
  loading,
  error: loadError,
} = useAsync(
  () =>
    Promise.all([
      getIncidents({
        status: filterStatus || undefined,
        category: filterCategory || undefined,
      }),
      getIncidentsSummary(),
    ]).then(([incidentsData, summaryData]) => ({
      incidents: incidentsData,
      summary: summaryData,
    })),
  [filterStatus, filterCategory],
);

// Los estados loading/error locales del CRUD se manejan con useCrudForm
```

**Beneficio:** elimina ~15 líneas de boilerplate de carga por componente (30 líneas totales).

---

## 3. Frontend 2: Website (HTML + Vanilla JS)

### 3.1. Caso A: Registro duplicado de event listeners

#### Por qué elegí este componente

El archivo `validation.js` en la raíz del proyecto maneja la validación del formulario de `application.html`. Dentro del mismo, hay **dos bloques de código casi idénticos** que registran los mismos event listeners (`input` y `blur`) para distintos conjuntos de campos:

```javascript
// BLOQUE 1 — requiredFieldIds (9 campos)
requiredFieldIds.forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;
    field.addEventListener("input", () => {
      hideSuccess();
      validateField(id);
    });
    field.addEventListener("blur", () => {
      validateField(id);
    });
});

// BLOQUE 2 — jobTitle y companyWebsite (2 campos opcionales)
["jobTitle", "companyWebsite"].forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;
    field.addEventListener("input", () => {
      hideSuccess();
      validateField(id);
    });
    field.addEventListener("blur", () => {
      validateField(id);
    });
});
```

La única diferencia entre ambos bloques es el array de IDs que se itera. El resto del código es **exactamente igual**.

#### Cómo lo refactorizaría

Extraería el patrón a una función `setupFieldValidation(fieldIds)` que se reutilice para ambos grupos.

**Implementación propuesta:**

```javascript
function setupFieldValidation(fieldIds) {
  fieldIds.forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;

    field.addEventListener("input", () => {
      hideSuccess();
      validateField(id);
    });

    field.addEventListener("blur", () => {
      validateField(id);
    });
  });
}

// En lugar de los dos bloques duplicados:
setupFieldValidation(requiredFieldIds);
setupFieldValidation(["jobTitle", "companyWebsite"]);
```

**Beneficio:** elimina ~12 líneas duplicadas (el 100% del segundo bloque). Además, si en el futuro se añaden más campos con validación, solo hay que añadirlos al array — no se duplica el código de registro de eventos.

---

### 3.2. Caso B: Validación de grupos checkbox/radio

#### Por qué elegí este componente

Tres funciones de validación en `validation.js` siguen exactamente el mismo patrón estructural:

| Función | Obtiene elemento(s) | Comprueba | Error |
|---|---|---|---|
| `validateServices()` | `form.querySelectorAll('input[name="services"]:checked')` | `length > 0` | `"Selecciona al menos un servicio."` |
| `validatePriorityArea()` | `form.querySelector('input[name="priorityArea"]:checked')` | truthy | `"Selecciona un area prioritaria."` |
| `validatePrivacyConsent()` | `document.getElementById("privacyConsent")` | `field.checked` | `"Debes aceptar el tratamiento..."` |

Las tres hacen lo mismo:
1. Obtienen el/los elementos del DOM
2. Comprueban si la condición se cumple
3. Si no, escriben un mensaje de error en el nodo correspondiente
4. Devuelven `true`/`false` indicando si la validación pasó

#### Cómo lo refactorizaría

Crearía una función genérica `validateCheckboxGroup` que acepte un selector y un mensaje de error, eliminando la repetición de la estructura.

**Implementación propuesta:**

```javascript
/**
 * Valida que al menos un checkbox de un grupo esté seleccionado.
 * @param {string} name - atributo name del grupo de checkboxes
 * @param {string} message - mensaje de error si ninguno está seleccionado
 * @returns {boolean} true si hay al menos uno seleccionado
 */
function validateCheckboxGroup(name, message) {
  const checked = form.querySelectorAll(`input[name="${name}"]:checked`).length;
  const errorNode = document.getElementById(`error-${name}`);
  if (errorNode) errorNode.textContent = checked > 0 ? "" : message;
  return checked > 0;
}

/**
 * Valida que un checkbox individual esté marcado.
 * @param {string} id - id del checkbox
 * @param {string} message - mensaje de error si no está marcado
 * @returns {boolean} true si está marcado
 */
function validateSingleCheckbox(id, message) {
  const field = document.getElementById(id);
  const errorNode = document.getElementById(`error-${id}`);
  if (!field || !errorNode) return true;

  const valid = field.checked;
  errorNode.textContent = valid ? "" : message;
  return valid;
}

// Uso en validateAll():
function validateAll() {
  const fieldResults = requiredFieldIds.map((id) => validateField(id));

  validateField("jobTitle");
  validateField("companyWebsite");

  const servicesValid = validateCheckboxGroup("services", "Selecciona al menos un servicio.");
  const priorityAreaValid = validateCheckboxGroup("priorityArea", "Selecciona un área prioritaria.");
  const privacyValid = validateSingleCheckbox("privacyConsent", "Debes aceptar el tratamiento de datos para continuar.");

  return fieldResults.every(Boolean) && servicesValid && priorityAreaValid && privacyValid;
}

// Las funciones originales validateServices, validatePriorityArea y validatePrivacyConsent
// ya no son necesarias y pueden eliminarse.
```

**Beneficio:** elimina ~20 líneas de las tres funciones `validateServices()`, `validatePriorityArea()` y `validatePrivacyConsent()` reemplazándolas con 3 llamadas de una línea cada una.

---

## 4. Impacto estimado del refactor

| Componente / Archivo | Antes (líneas aprox.) | Después (líneas aprox.) | Reducción |
|---|---|---|---|
| `IncidentsManagerClient.tsx` | ~600 | ~530 | **~12 %** |
| `SuppliersManagerClient.tsx` | ~600 | ~530 | **~12 %** |
| `validation.js` | ~200 | ~170 | **~15 %** |
| **Nuevo archivo** `useCrudForm.ts` | — | +45 | Nuevo hook |

**Resumen de código eliminado:** ~170 líneas de lógica duplicada entre ambos frontends.

**Otros beneficios:**

- **Mantenibilidad:** los bugs en el flujo CRUD se corrigen en un solo lugar (`useCrudForm`) en lugar de tener que parchear dos componentes
- **Consistencia:** todos los futuros componentes CRUD usarán la misma lógica de validación, carga y error
- **Testabilidad:** los hooks son más fáciles de testear de forma aislada que la lógica embebida en componentes
- **Legibilidad:** los componentes se quedan principalmente con JSX y configuración, facilitando la revisión del código

---

*Fin del reporte de auditoría.*