# Spec: reorganizacion mobile-first del backoffice Nexova

## 1. Objetivo y alcance

Convertir el backoffice en un espacio de trabajo profesional, ordenado y facil de manejar en movil y ordenador. Priorizar la tarea del usuario sobre el catalogo de herramientas: navegacion estable, acciones contextuales y contenido legible.

Esta spec define un cambio de presentacion y arquitectura de informacion en `uis/backoffice`. No modifica contratos API, reglas de negocio, permisos, autenticacion, datos ni URLs existentes. No incluye cambios en el website publico ni nuevas funcionalidades de negocio.

## 2. Revision de la interfaz actual

Revision estatica del codigo, no auditoria visual ejecutada en navegador:

- `components/NavBar.tsx` presenta siete enlaces de navegacion, la accion global "Registrar nueva", perfil y salida junto a la marca, en una fila sin alternativa de menu movil. Hay riesgo de desbordamiento o compresion en anchos pequenos.
- El alta de candidaturas aparece incluso fuera de seleccion. Su etiqueta no identifica que se registra y ocupa espacio global para una tarea local.
- La navbar no tiene un estado activo de ruta. La identidad del usuario puede mostrar un correo largo sin una restriccion explicita de ancho.
- `app/page.tsx` repite un catalogo de herramientas, pero no coincide con la navbar: incluye proveedores y telemetria, mientras omite inventario y reporte semanal.
- El inicio dedica espacio a una presentacion y tarjetas con descripciones y botones repetidos, en lugar de facilitar el acceso operativo directo.
- `app/layout.tsx` monta la misma navbar en todo el arbol, incluidas las paginas de autenticacion, y aplica una cuadricula decorativa global.
- `app/globals.css` combina sombras, superficies redondeadas y fondo cuadriculado. Es una base de marca aprovechable, pero necesita menos decoracion y una jerarquia mas funcional.
- `components/IncidentsManagerClient.tsx` combina resumen, filtros, formulario y listado en una pantalla; el formulario precede al listado en el flujo y la tabla requiere desplazamiento horizontal.

Hipotesis de diseno: separar destinos globales, cuenta y acciones locales reducira la saturacion sin perder acceso a ninguna herramienta. Comprobacion discriminante: a 360 px y 1280 px, poder abrir cualquier modulo desde el menu, identificar la seccion activa y ejecutar una accion del modulo sin desbordamiento horizontal de pagina. Si requiere buscar acciones entre herramientas ajenas, la propuesta no cumple.

## 3. Recomendacion principal

Adoptar un shell de aplicacion con tres piezas:

1. Cabecera compacta: marca, control de menu cuando corresponda y menu de cuenta. Sin catalogo de herramientas ni botones de creacion globales.
2. Navegacion lateral agrupada: persistente en escritorio; panel modal desplegable en movil y tablet.
3. Area de trabajo: contexto de pagina, titulo, accion principal y contenido del modulo.

No introducir una barra inferior adicional, un menu "Mas" con herramientas mezcladas ni una segunda navbar global. Evitar duplicar controles y patrones de navegacion.

## 4. Arquitectura de informacion

Mantener las URLs; cambiar unicamente las etiquetas visibles y su agrupacion. Las cabeceras de grupo no son destinos ni requieren rutas nuevas.

| Grupo | Etiqueta visible | Ruta existente |
| --- | --- | --- |
| General | Inicio | `/` |
| Seleccion | Candidaturas | `/talent-pipeline-tracker` |
| Operaciones | Inventario | `/inventory/products` |
| Operaciones | Incidencias | `/incidents` |
| Operaciones | Proveedores | `/suppliers` |
| Conocimiento | Asistente comercial | `/knowledge` |
| Analitica | Analizador de incidentes | `/incident-analyzer` |
| Analitica | Reporte semanal | `/reporting` |
| Analitica | Telemetria tecnica | `/telemetry` |

- Mostrar todos los destinos autorizados en el mismo orden en movil, escritorio e inicio. No ocultar modulos por una jerarquia de roles inventada.
- Usar una unica configuracion de navegacion tipada, consumida por sidebar, panel movil e inicio, para evitar catalogos divergentes.
- Mantener los grupos expandidos inicialmente. No anadir acordeones hasta que exista una necesidad real de espacio.
- Marcar el destino activo con fondo, indicador y `aria-current="page"`, no solo con color. Las rutas de detalle y alta activan su modulo padre mediante coincidencia de segmentos, no prefijos ambiguos.
- Inventario tendra navegacion local hacia Productos (`/inventory/products`) y Ordenes (`/inventory/orders`). Entrada y salida se mantienen en `/inventory/orders/inbound` y `/inventory/orders/outbound`, como acciones contextuales de ordenes.
- El perfil (`/account/profile`) y cerrar sesion pasan al menu de cuenta. Conservar las demas rutas de cuenta existentes, sin renombrarlas ni eliminarlas.
- Las pantallas de login, registro y recuperacion usan un layout sencillo de autenticacion, sin sidebar ni navegacion operativa. Conservar redirecciones y proteccion de rutas existentes.

## 5. Distribucion responsive

Implementar primero el flujo de una columna y ampliar por espacio disponible, no por deteccion de dispositivo.

| Ancho CSS | Navegacion | Area de trabajo |
| --- | --- | --- |
| Menos de 768 px | Boton de menu y panel modal lateral | Una columna; margen de 16 px; acciones apiladas cuando sea necesario |
| 768 a 1023 px | Mismo panel modal, sin sidebar fija | Margen de 24 px; dos columnas solo si el contenido sigue siendo legible |
| Desde 1024 px | Sidebar persistente de 240 px | Contenido flexible con `min-width: 0`; margen de 24 a 32 px |

### Cabecera y navegacion

- Cabecera de referencia de 56 px en movil y 64 px en escritorio; marca compacta y avatar con dimensiones estables. No mostrar el correo completo en la cabecera movil.
- Sidebar con marca, destinos agrupados y scroll propio si el alto no basta. El contenido y la navegacion no deben quedar inaccesibles en ventanas bajas.
- Panel movil de hasta 320 px y nunca mayor que el viewport, con fondo superpuesto y boton de cierre visible. Bloquear el scroll de fondo mientras este abierto.
- Abrir mediante un boton con icono de menu, nombre accesible, `aria-expanded` y `aria-controls`.
- Gestionar el panel como dialogo modal: foco inicial, foco contenido, cierre con Escape, cierre al seleccionar destino y devolucion del foco al disparador cuando siga presente.
- Al cambiar de breakpoint, retirar bloqueo de scroll y estado modal sobrantes. No dejar controles invisibles alcanzables con Tab.
- No fijar barras de acciones inferiores por defecto. Si un flujo exige una, reservar su espacio y respetar `safe-area-inset-bottom` y el teclado virtual.

### Contenido de pagina

- Un unico `main` y un unico `h1` por pantalla. El shell aporta el landmark principal; adaptar los `main` existentes para evitar anidarlos.
- Encabezado local con titulo literal, contador o contexto cuando exista y una accion principal del modulo.
- Breadcrumbs para detalles y formularios, no para decorar el inicio. En movil mostrar al menos el retorno al listado padre.
- Formularios y lectura con ancho maximo aproximado de 720 px; listados aprovechan el ancho restante sin estrecharse artificialmente.
- No usar altura fija en bloques con texto variable. Cabeceras, etiquetas y botones pueden crecer o apilarse; nunca cortar nombres de acciones.

## 6. Inicio operativo

- Sustituir el bloque de presentacion por un encabezado compacto "Inicio".
- Presentar los destinos por los mismos grupos del menu, en listas de enlaces con icono y nombre. Una columna en movil; dos o tres en escritorio segun espacio.
- La fila completa sera el enlace, con estado hover y foco visibles. Evitar repetir "Abrir herramienta" en cada elemento.
- No agregar descripciones de funcionalidades, instrucciones de uso, tarjetas promocionales, graficos ficticios ni indicadores sin datos reales.
- No crear nuevas peticiones de resumen solo para decorar el inicio. Favoritos, actividad reciente y busqueda global quedan fuera de esta iteracion.

## 7. Patrones de trabajo por modulo

### Listados y acciones

- Mostrar primero busqueda, resultados y accion principal; abrir formularios de alta o edicion solo cuando se soliciten. Evitar formularios vacios permanentes compitiendo con la tabla.
- Candidaturas: "Nueva candidatura" dentro del modulo, apuntando a `/talent-pipeline-tracker/Candidates/new`. Conservar busqueda, filtros, notas y detalle existentes.
- Incidencias y proveedores: alta contextual y edicion desde el registro. Mantener validaciones, confirmaciones y transiciones de estado.
- Inventario: separar Productos y Ordenes; entrada y salida como acciones explicitas. Mantener las validaciones actuales de stock.
- Analizador: conservar carga CSV, validacion, resultados y exportacion como pasos de un mismo flujo, sin repartirlo entre menus globales.
- Conocimiento: priorizar pregunta, respuesta y fuentes; conservar errores, estados de espera y referencias existentes.
- Reporting y telemetria: filtros junto al informe; indicadores solo con datos reales y estado sin datos cuando corresponda.
- Acciones de seed/demo e importaciones administrativas no deben competir con la accion principal. Ubicarlas en un menu secundario y conservar las restricciones reales de acceso.

### Busqueda y filtros

- Campo de busqueda con etiqueta accesible y ancho flexible. No introducir busqueda global en esta fase.
- En movil, conservar busqueda y boton "Filtros" con contador de filtros activos. Abrir filtros en panel o dialogo accesible; aplicar y limpiar de forma explicita.
- En escritorio, filtros frecuentes visibles en una fila que pueda envolver; los avanzados pueden ir en el mismo panel.
- Mostrar filtros aplicados y permitir eliminarlos. Conservar busqueda, filtros y pagina al volver de un detalle, mediante URL para valores no sensibles o estado local para datos personales; nunca incluir tokens en la URL.

### Tablas y detalle en movil

- No encoger una tabla de escritorio hasta volverla ilegible. Para listados operativos, mostrar filas apiladas con identificador, estado y dos o tres datos prioritarios del mismo registro.
- Acceder al resto de campos mediante detalle; mantener todas las acciones disponibles, agrupando las secundarias en un menu accesible.
- En informes donde la comparacion por columnas sea imprescindible, permitir scroll horizontal solo dentro de una region identificada y accesible por teclado. La pagina completa no debe desplazarse horizontalmente.
- Usar la misma fuente de datos y logica para las variantes responsive. No duplicar peticiones, reglas CRUD ni elementos interactivos en el arbol accesible.
- Formularios de una columna en movil; dos columnas en escritorio solo para campos relacionados. Etiquetas persistentes, errores junto al campo y foco en el primer error tras envio.
- Formularios largos como pagina o panel de pantalla completa en movil; no dentro de un modal pequeno con scroll anidado. Confirmar el descarte de cambios sin guardar.

## 8. Direccion visual

Estilo de herramienta profesional: superficies sobrias, jerarquia clara y densidad moderada, sin apariencia de landing page.

- Reutilizar las fuentes locales: Geist para interfaz y texto; Outfit reservado a marca o titulos puntuales. No descargar fuentes externas.
- Base neutra clara (`#f7f8fa`), superficies blancas, texto oscuro (`#202428`) y bordes discretos (`#dfe3e6`). Mantener el verde de marca `#0f766e` para seleccion y accion principal.
- Reservar rojo, ambar y verde de estado a significado operativo; acompanar siempre de texto o icono. No convertir toda la interfaz en variaciones del verde de marca.
- Definir tokens compartidos de color, espaciado, tipografia, foco y radios. Escala de espacio: 4, 8, 12, 16, 24 y 32 px.
- Texto base de 16 px en movil; texto secundario o tabla de al menos 14 px; titulos de pagina entre 24 y 28 px, sin escalar tipografia con unidades de viewport ni espaciado negativo.
- Radio de 6 a 8 px en controles y elementos enmarcados. Reservar circulos para avatares e indicadores. Eliminar pildoras de navegacion, cuadricula de fondo global y sombras grandes.
- Secciones sin tarjetas contenedoras ni tarjetas anidadas; usar separadores y espacio. Tarjetas solo para items repetidos o herramientas que realmente necesiten marco.
- Acciones primarias con texto explicito; acciones auxiliares con iconos reconocibles y nombre accesible. Tooltips en escritorio para iconos sin etiqueta; no depender de hover para entenderlos en tactil.
- No hay libreria de iconos declarada actualmente. Al implementar, valorar `lucide-react` como unica libreria; no dibujar SVG manuales ni anadir varias dependencias equivalentes. Cualquier cambio del lockfile protegido necesita autorizacion previa.
- Transiciones discretas de 120 a 180 ms; respetar `prefers-reduced-motion`. Sin animaciones decorativas ni cambios de geometria al hacer hover.

## 9. Accesibilidad y estados

- Objetivo WCAG 2.2 AA: contraste de texto normal minimo 4.5:1 y de controles/indicadores relevantes 3:1. Validar los pares finales, no asumir que los tokens garantizan contraste.
- Objetivos tactiles de al menos 44 x 44 px, con separacion suficiente; el icono puede ser menor que su area interactiva.
- Navegacion completa por teclado, enlace para saltar al contenido, foco visible no tapado por cabeceras y orden de lectura coherente.
- Menu de cuenta operable por teclado, con perfil y salida separados de los destinos de negocio. Correos y nombres largos no alteran el ancho del shell; mostrar el valor completo en perfil.
- Carga con placeholders estables; envio con bloqueo contra duplicados; exito perceptible; estados vacios y errores recuperables con mensajes breves y accion pertinente.
- Errores de formulario y cambios relevantes anunciados de forma accesible, sin exponer datos sensibles. Borrado con confirmacion que identifique el registro.
- Mantener acceso a contenido y controles con zoom al 200%, y reflow equivalente a 320 px. No depender exclusivamente de color, hover o gestos.

## 10. Directrices tecnicas y secuencia de implementacion

Reutilizar Next.js App Router, React, TypeScript, Tailwind, `Providers` y `useAuth`. No introducir otro framework o design system completo.

1. **Shell y navegacion:** crear configuracion comun de destinos y los componentes minimos para cabecera, sidebar/panel y cuenta. Sustituir `NavBar` y separar layout autenticado de autenticacion sin cambiar URLs. Si se usan route groups, mover solo lo necesario y mantener intactos los handlers de `app/api`.
2. **Inicio y estilos base:** aplicar tokens, retirar decoracion global y sustituir el catalogo por accesos agrupados. Revisar los anchos y `main` existentes para que el shell no produzca doble padding o landmarks anidados.
3. **Modulos:** adaptar primero candidaturas e incidencias como patrones de listado/formulario; despues proveedores e inventario; finalmente analizador, conocimiento e informes. Reutilizar logica y componentes adecuados, sin refactor ajeno al rediseno.
4. **Validacion:** comprobar rutas, autenticacion, responsive, accesibilidad y los flujos existentes antes de dar por terminada cada fase.

Los componentes de navegacion interactivos seran cliente; no convertir indiscriminadamente las paginas de datos en Client Components. No duplicar caches, efectos ni llamadas por presentar variantes moviles.

Antes de escribir codigo Next.js, consultar las guias locales indicadas en `uis/backoffice/AGENTS.md`. Respetar rutas protegidas del repositorio: si el trabajo requiere modificar archivos de memoria, README o lockfiles protegidos, solicitar autorizacion antes de editarlos.

## 11. Criterios de aceptacion

- [ ] Todos los destinos del mapa estan disponibles y mantienen sus URLs, tanto desde movil como desde escritorio.
- [ ] La cabecera no contiene enlaces de herramientas ni el alta global de candidaturas. Perfil y salida estan en el menu de cuenta.
- [ ] El inicio y ambas navegaciones consumen el mismo catalogo, sin omitir proveedores, inventario, reporting o telemetria.
- [ ] La ruta activa es reconocible en listados, detalles y formularios. El regreso al listado conserva su contexto.
- [ ] A 320, 360, 390, 768, 1024 y 1440 px no hay scroll horizontal de pagina, solapamientos ni controles cortados. Solo las tablas analiticas justificadas tienen scroll local.
- [ ] A ambos lados de los breakpoints 768 y 1024 px, y al rotar el dispositivo, no quedan overlays, bloqueos de scroll ni controles ocultos enfocables.
- [ ] El panel movil y el menu de cuenta se pueden abrir, recorrer y cerrar con teclado; el foco vuelve correctamente y el fondo modal no es interactivo.
- [ ] Objetivos tactiles, contraste, zoom y lector de pantalla cumplen las reglas de accesibilidad anteriores.
- [ ] Nombres/correos largos, muchos registros, resultados vacios, carga, error y formularios invalidados no rompen la distribucion.
- [ ] Listados y formularios resultan utilizables en movil sin perder campos, filtros, acciones o validaciones de negocio.
- [ ] Login, cierre de sesion, redireccion tras autenticacion y acceso directo a rutas protegidas conservan su comportamiento.
- [ ] No cambian payloads API, permisos ni reglas de stock, estados, exportacion o notas. No aparecen nuevas peticiones por duplicar vistas responsive.

### Verificacion de la implementacion futura

- Ejecutar lint/typecheck del area tocada y las pruebas existentes relacionadas; no usar la suite completa repetidamente ni crear pruebas nuevas sin solicitud explicita.
- Hacer recorrido manual o con Playwright y guardar capturas de inicio, listado, formulario y menu movil en 360 x 800 y 1440 x 900; comprobar ademas los anchos indicados arriba.
- Recorrer con teclado y lector de pantalla al menos navegacion, filtros, formulario y confirmacion de borrado.
- Comprobar un flujo representativo por modulo con datos controlados, sin crear ni borrar registros de produccion durante la validacion.
- Registrar fallos preexistentes por separado; no ampliar el alcance para corregirlos. Esta entrega documental no acredita todavia ninguna de estas verificaciones de interfaz.