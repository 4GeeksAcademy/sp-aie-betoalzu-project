El proyecto va de maravilla. Pero ahora, necesito hacer una batería de pruebas para la api de autenticación, para prubar de que todo va bien, sin errores o algo que esté fallando.

## tarea

Antes de implementar algo, necesito lo siguiente:

- un archivo testing.md en la raiz del repositorio, donde se documente, como ejecutar las pruebas,  que casos decidiste curbir y por que, entre otras cosas que consideres importante de incluir
- agrega los casos que planeas construir
- Estos son los requisitos de los casos:
   - La batería de pruebas debe cubrir todos los endpoints de la API de autenticación
    - Cada endpoint debe tener como mínimo: una prueba de camino feliz, una prueba de caso límite y una prueba de modo de fallo
    - Usar pytest para el backend en FastAPI y Jest para la lógica en TypeScript
    - Las pruebas deben pasar limpiamente con `uv run pytest` y `jest --coverage`
    - No probar la serialización HTTP — probar la lógica