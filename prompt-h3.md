# Tarea
## Vistas y navegación
    -Crea una pagina donde se vea todas las candidaturas (/) donde muestren los candidatos obtenidos con GET/records
    -Crea una página de detalle de candidatura (/Candidates/[id]) que obtenga todos los datos con GET/records/:id
    *La navegación entre ambas páginas deben usar rutas de Next.js, sin cargas completas de la página

## Listado de candidaturas
    -Muestra el nombre completo, el puesto, el estado actual y la etapa actual de cada candidato.
    -Implementa filtro por estado y filtro por etapa usando query parameters (useSearchParams).
    -Implementa un campo de búsqueda que filtre por nombre o email sin recargar la página.
    -Muestra un estado de carga mientras se obtienen los datos y un mensaje de error si la petición falla.

## Detalle de candidatura
    -Muestra todos los campos disponibles: nombre, email, teléfono, puesto, LinkedIn, enlace al CV, años de experiencia, estado, etapa y fecha de aplicación.
    -Incluye un control para actualizar el estado mediante PATCH /records/:id.
    -Incluye un control para actualizar la etapa mediante PATCH /records/:id.
    -Muestra el listado de notas obtenidas desde GET /records/:id/notes.
    -Permite añadir una nueva nota mediante POST /records/:id/notes.
    -Permite eliminar una nota mediante DELETE /records/:id/notes/:note id.

## Gestión de candidaturas
     -Incluye un formulario para registrar una nueva candidatura (POST/records ).
    -Incluye un formulario para editar los datos de una candidatura (PUT/records/:id).
    *Ambos formularios deben validar los campos requeridos antes de enviarse.
    *Muestra feedback de éxito o error tras cada envío.

## Estado y manejo asíncrono
    -Todas las llamadas a la API deben gestionarse con async/await
    -Cada operación de obtención de datos debe tener al menos tres estados en la UI: cargando, éxito y error.
    -Tras un PATCH, PUT O POST, actualiza la interfaz para reflejar el cambio sin requerir una recarga completa de página.

## Estructura del código
    -Organiza el proyecto con una estructura de carpetas clara: /components, /hooks (si aplica), /types /lib o/services
    -Define tipos TypeScript para todas las estructuras de datos recibidas de la API.

IMPORTANTE: Los nombres de campos, etiquetas visibles, estados y valores específicos del dominio en tu implementación deben coincidir con lo especificado en tu CONTEXT.md. Por ejemplo, si tu empresa es TrackFlow, la interfaz debe sentirse como una herramienta interna del equipo de People & Talent de TrackFlow, aunque los nombres de campos de la API sigan siendo los definidos por el tracker backend. Una implementación genérica que ignore el contexto de tu empresa no será aceptada.

⚠️ IMPORTANTE: Usa únicamente Next.js (App Router), React y TypeScript. No uses librerías externas de gestión de estado (Redux, Zustand, Jotai, etc.). El estado a nivel de componente con hooks es suficiente para este hito.