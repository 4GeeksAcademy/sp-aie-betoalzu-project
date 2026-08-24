# REPORT — Auditoría y Refactorización de Frontends

> **Fecha:** 2026-08-24
> **Rama:** `feat/auditory`
> **Alcance:** `uis/` (backoffice Next.js + website HTML vanilla) y `validation.js`
> **Base:** Auditoría previa documentada en [`AUDIT.md`](./AUDIT.md)

---

## 1. Contexto

Se realizó una auditoría completa de los frontends del proyecto (backoffice y website corporativo) utilizando las skills instaladas de rendimiento y Core Web Vitals. La auditoría se documentó en `AUDIT.md` y, posteriormente, se procedió a implementar las acciones críticas y altas identificadas, con **un commit por cada problema resuelto**.

---

## 2. Cambios realizados

### 2.1. Website — Migración de Tailwind CDN a CSS compilado

**Commit:** `fix/website-migracion-a-tailwind-css-compilado`

- **Qué:** Se reemplazó la carga de Tailwind vía CDN (JS) por un CSS compilado estáticamente con la CLI de Tailwind.
- **Por qué:** El script del CDN bloqueaba el renderizado y añadía un round-trip de red adicional. Compilar localmente elimina el bloqueo y reduce las peticiones.
- **Archivos:** `uis/website/index.html`, `uis/website/application.html`, `uis/website/src/styles.css`, `uis/website/dist/styles.css`, `uis/website/package.json`.

### 2.2. Website — Preload del LCP (hero image)

**Commit:** `fix/website-preload-lcp-hero-image`

- **Qué:** Se añadió `<link rel="preload" as="image" fetchpriority="high">` para la imagen hero y atributos `fetchpriority="high"`, `loading="eager"`, `decoding="sync"` y dimensiones explícitas.
- **Por qué:** La imagen hero era el Largest Contentful Paint (LCP); precargarla reduce drásticamente el tiempo hasta el LCP.

### 2.3. Backoffice — Modo producción en contenedor

**Commit:** `fix/start-sh-modo-produccion`

- **Qué:** `start.sh` pasó de `npm run dev` a `npm run build && npm start`; el website compila su CSS Tailwind antes de servirse.
- **Por qué:** El servidor de desarrollo (dev) no está optimizado para producción y supone un riesgo de rendimiento y seguridad.

### 2.4. Backoffice — Consolidación del proxy de backend

**Commit:** `fix/backoffice-consolidar-backend-proxy`

- **Qué:** Se consolidaron 4 funciones `_shared.ts` duplicadas en un único `lib/backend-proxy.ts` con `proxyToBackend()`, unificando además la resolución de la URL del backend.
- **Por qué:** Había lógica duplicada (~50 líneas) y criterios inconsistentes de resolución de URL entre módulos (auth vs incidents/inventory).
- **Archivos:** `uis/backoffice/lib/backend-proxy.ts`, y los `_shared.ts` de `auth`, `profiles`, `incidents` e `inventory`.

### 2.5. Backoffice — Refactor CRUD de IncidentsManagerClient

**Commit:** `fix/backoffice-incidents-crud-refactor`

- **Qué:** Se refactorizó `IncidentsManagerClient.tsx` para usar el nuevo hook genérico `useCrudForm`, eliminando ~80 líneas de estado manual duplicado.
- **Por qué:** El patrón CRUD (resetForm, validateForm, onEdit, onSubmit, onDelete) estaba duplicado prácticamente idéntico entre Incidentes y Proveedores.
- **Además:** Se añadieron imports dinámicos (`next/dynamic`) para cargar componentes pesados de forma perezosa.
- **Archivos:** `hooks/useCrudForm.ts`, `components/IncidentsManagerClient.tsx`, `app/incidents/page.tsx`.

### 2.6. Backoffice — Refactor CRUD de SuppliersManagerClient

**Commit:** `fix/backoffice-suppliers-crud-refactor`

- **Qué:** Se refactorizó `SuppliersManagerClient.tsx` con el mismo hook `useCrudForm`, eliminando otra ~80 líneas de lógica CRUD duplicada.
- **Por qué:** Misma duplicación que en Incidentes; se reutiliza el hook recién creado.

### 2.7. Website — Refactor de `validation.js`

**Commit:** `fix/website-refactor-validation-js`

- **Qué:** Se extrajeron las funciones reutilizables `setupFieldValidation(fieldIds)`, `validateCheckboxGroup(name, message)` y `validateSingleCheckbox(id, message)`, eliminando la duplicación de event listeners y de lógica de validación de grupos.
- **Por qué:** Había ~12 líneas de registro de listeners duplicadas y ~15 líneas de validación de grupos repetidas, además de una función `setGroupError` que quedó como código muerto.

### 2.8. Backoffice — Limpieza post-refactor

**Commit:** `fix/backoffice-eliminar-setError-duplicado`

- **Qué:** Se eliminaron funciones duplicadas (`onTransition`, `handleSeed`) que referenciaban el `setError` ya eliminado, y se corrigió `onToggleStatus` para usar `setPageError`.
- **Por qué:** Tras el refactor quedaron restos del código anterior que rompían el build de TypeScript.

---

## 3. Resumen cuantitativo

| Área | Cambio | Líneas eliminadas aprox. |
|---|---|---|
| Backoffice | Hook `useCrudForm` + 2 refactors | ~160 |
| Backoffice | Proxy unificado | ~50 |
| Backoffice | Dynamic imports | — |
| Website | Tailwind compilado | — |
| Website | `validation.js` refactor | ~25 |

**Resultado:** `0` errores de TypeScript en el backoffice tras todos los cambios.

---

## 4. Cambio más crítico

El cambio **más crítico** fue **`fix/website-migracion-a-tailwind-css-compilado`**,

y tiene dos motivos de peso:

1. **Bloqueo del renderizado:** El script del CDN de Tailwind era **render-blocking**. Mientras ese script se descargaba y ejecutaba, el navegador no podía pintar la página, lo que degradaba directamente el **LCP** y la experiencia percibida de carga de la landing page corporativa, la puerta de entrada del negocio.

2. **Eliminación de dependencia externa en runtime:** Compilar el CSS localmente elimina una dependencia de un tercero en tiempo de ejecución, lo que aporta **fiabilidad** (no depende de red/uptime del CDN), **velocidad** (menos peticiones) y **seguridad** (no se ejecuta JS de terceros).

Este cambio es la base que habilita y complementa al resto de optimizaciones de rendimiento (preload del LCP, producción en contenedor), por lo que se considera la acción con mayor impacto neto de toda la iteración.