En uis, la esctructura debe estar separada,  
- directorio `uis/website` contiene lo público
- `uis/backoffice` contiene todo lo privado

## Estructura de uis/backoffice
- Una aplicación principal de administrador que tenga acceso a distintas herramientas que vayamos implementando. Por ahora solo está el 'talent pipline tracker'
- La app principal debe ser un menú, en donde se pueda tener acceso facil a las herramientas
- las herramientas tambien deben estár adentro de `uis/backoffice` fusionada con la aplicación principal

## tarea
- realiza la aplicación principal en `uis/backoffice` e integra en la estructura de la misma el "talent-pipeline-tracker"
- luego de integrada la herramienta "talent-pipeline-tracker" a la app principal, borrar la carpeta con el mismo nombre que ahora mismo se encuentra en `uis/backoffice`. Cuestión que, terminada la app, solo quede la app dentro de la ruta y nada más