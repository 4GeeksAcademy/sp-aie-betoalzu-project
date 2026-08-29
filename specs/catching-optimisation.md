# Tarea
## Frontend
- Analiza el backoffice(`uis/backoffice`) e identifica que componente o ruta puede ser una buen candidato para una lazy loading
- A los componentes o rutas que veas como candidatas, implementales el Lazy loading usando `React.lazy`
- Con los componentes, analiza cuales son los más costosos de renderizar, y sea recomendable aplicar `useMemo` donde el cálculo no sea trivial y el array de dependencias esté bien definido
- Aplica el useMemo a los componentes elegidos. No lo apliques a cálculos triviales

## Análisis y optimización del backend
- Lista todos los endpoints de tu aplicación FastAPI. Para cada uno, evalúa: (a) ¿cuánto cuesta la operación? (b) ¿con qué frecuencia se Ilama? (c) ¿con qué frecuencia cambian los datos subyacentes?
- Identifica al menos dos endpoints que cumplan los criterios de coste + frecuencia + estabilidad para el caching.
- Implementa el caching para esos endpoints. Puedes usar un diccionario en memoria con lógica de TTL, functools.lru_cache donde aplique, o una caché basada en Redis si tu stack lo soporta.
- Implementa la invalidación de caché: si los datos subyacentes cambian (por ejemplo, una operación de escritura), los valores cacheados relevantes deben limpiarse o marcarse como obsoletos.
⚠️ IMPORTANTE: No cachees endpoints que devuelvan datos personalizados, de sesión o sensibles sin acotar la clave de caché al usuario autenticado. Una clave de caché compartida para datos privados es una fuga de datos, no una mejora de rendimiento.

## Informe técnico
- Escribe un CACHING_REPORT.md (o equivalente) en tu monorepo con las siguientes secciones:
- Decisiones en el frontend: qué componentes se cargaron de forma diferida y por qué; qué valores se memoizaron y cuál es el beneficio medido o estimado.
- Decisiones en el backend: para cada endpoint cacheado, documenta el coste de la operación, la frecuencia estimada de Ilamadas, el TTL elegido y la estrategia de invalidación.
- Intercambios reconocidos: al menos una discusión explícita sobre el intercambio entre frescura y rendimiento - dónde elegiste un TTL concreto y por qué ese nivel de potencial desactualización es aceptable para este caso de uso.
- Qué no se cacheó y por qué: identifica al menos un endpoint o componente que consideraste pero decidiste no cachear, con justificación.