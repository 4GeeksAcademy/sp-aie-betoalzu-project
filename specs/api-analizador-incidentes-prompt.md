# Tarea
- crea en la raíz `services/api`
- Crea un endpoint `POST/api/incidents/analyze` que acepte un fichero CSV como multipart/form-data
- El endpoint debe ejecutar la misma lógica de validación y análisis que el script y devolver el resumen en JSON.
- Crea un endpoint `GET/api/incidents/results/export` que devuelva el último análisis en formato CSV descargable.
- Los errores (fichero vacío, formato incorrecto) deben devolver respuestas HTTP apropiadas con mensaje descriptivo.