# Auditoria de ciberseguridad de Nexova

Fecha: 2026-10-28. Base inspeccionada: `7e42ec2`.
Estado: **NO APROBADO**. Informe en elaboracion; quedan controles pendientes.
No se han consultado datos personales, credenciales ni servicios de terceros
con informacion del repositorio. Los ejemplos y pruebas usan datos sinteticos.

## Evidencia critica: SEC-01, lectura arbitraria de archivos

Severidad critica, confianza 10/10. Antes de la correccion,
`server.py:113-126` registraba `GET /{path:path}` sin autenticacion y construia
una ruta con `os.path.join` sobre la raiz del proyecto. Exponia archivos
internos, directorios con `index.html`, enlaces simbolicos y traversal.
Impacto: posible descarga de configuracion, claves y bases locales y,
por tanto, compromiso de cuentas. No se descargaron esos archivos reales.

Reproduccion previa ejecutada: extraccion AST de la funcion real en una app
FastAPI minima, con `httpx.ASGITransport`, raiz y canarios temporales.

```text
/private-canary.txt: status=200, synthetic_canary_exposed=True
/..%2Foutside-canary.txt: status=200, synthetic_canary_exposed=True
```

Correccion: retirar el catch-all que servia la raiz del repositorio; no
intentar filtrar extensiones o normalizar traversal manteniendo la exposicion.
Las interfaces se sirven separadamente; se conserva `GET /` y el registro
de routers de la API. Una URL no registrada devuelve ahora 404.

Regresion reproducible sin credenciales ni red:

```sh
python -m pytest tests/security/test_static_files.py -q
```

La suite crea exclusivamente archivos temporales sinteticos (incluido un
archivo **falso** llamado `.env`), un enlace y un archivo fuera de la raiz.
Ejecuta las funciones reales extraidas por AST, sin inicializar proveedores,
bases del proyecto ni el lifespan completo. Verifica cuatro archivos privados,
traversal codificado, enlaces y conservacion del indice publico. Esta prueba
aislada no sustituye un smoke test del servidor completo.

Resultado posterior: **7 passed**; todas las peticiones a archivos privados,
traversal y enlaces devuelven 404, el indice devuelve 200. Ruff E9 sobre
servidor/pruebas y F sobre pruebas, y `git diff --check`: aprobados.

## Contencion operativa y confirmacion humana

Politica autorizada por el desarrollador: incidencias, analizador y API del
agente quedan limitados a `admin`/`manager`. Inventario exige autenticacion
en lecturas y roles operativos en escrituras; MCP autentica tambien sus GET
de productos con el token de servicio. No se afirma aislamiento por cliente:
el modelo de incidencias no contiene un tenant verificado y los operadores
autorizados comparten el conjunto de datos.

Toda resolucion de ticket requiere `confirm_resolution: true` (booleano
estricto), un actor autenticado y transicion valida. La UI solicita confirmacion;
se persisten `resolved_by` y `resolution_confirmed_at`. No se permite crear
directamente un ticket ya resuelto. MCP rechaza `resolved` antes de llamar
al backend incluso si el cliente tiene scope de escritura.
Esto verifica una confirmacion explicita en el flujo implementado, no una
prueba criptografica de presencia humana: un cliente API privilegiado puede
enviar el booleano. Separar identidades humanas/de servicio y doble aprobacion
es una recomendacion pendiente.

Pruebas offline reproducibles:

```sh
PYTHON_DOTENV_DISABLED=1 SECRET_KEY=synthetic-audit-only \
  python -m pytest tests/security/test_operations_controls.py \
  tests/security/test_briefing_injection.py tests/mcps/test_backend.py \
  tests/mcps/test_server.py -q
```

La prueba del briefing envia literalmente la instruccion de olvidar politicas
y acceder a otra cuenta. Exige bloqueo `instruction_override`, cero consultas
a RAG/LLM/tools, traza sin texto del ataque y respuesta de rechazo. No acredita
robustez universal frente a variantes ni escalacion automatica del caso;
esa escalacion no esta implementada.

Resultado: **38 passed** en controles operativos, caso de inyeccion, backend
MCP, servidor MCP y regresion de inventario. Ruff E9 y F en pruebas nuevas:
aprobados. ESLint focalizado: cero errores, dos warnings previos en
`services/api.ts` (variables no usadas).

Typecheck global intentado una vez: falla por cinco errores preexistentes en
`__tests__/services/rfp-sse.test.ts` (vitest ausente), `hooks/useRfpSse.ts`
(dos imports inexistentes), `services/chat-ws.ts` (`JWT_TOKEN_KEY` inexistente)
y `services/rfp-sse.ts` (reader posiblemente undefined). No se corrigieron
fuera de alcance. Un tsconfig temporal que extiende el original, limita
`include` a los archivos afectados y conserva `strict` verifica sus imports
transitivos correctamente. No se afirma que el build global pase.
