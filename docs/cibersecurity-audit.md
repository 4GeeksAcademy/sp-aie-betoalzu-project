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
