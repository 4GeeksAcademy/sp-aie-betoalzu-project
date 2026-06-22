# AGENTS.md

## Lectura obligatoria al iniciar cada sesion

Antes de ejecutar cambios, el agente debe leer estos archivos del banco de memoria en este orden:

1. memory-bank/projectbrief.md
2. memory-bank/techContext.md
3. memory-bank/CONTEXT.md
4. memory-bank/progress.md

Si alguno no existe o esta vacio, el agente debe reportarlo en su primer mensaje de estado.

## Flujo obligatorio antes de cada commit

El agente debe completar este flujo, en orden, antes de crear un commit:

1. Validar alcance de cambios:
   - Confirmar que los archivos modificados corresponden a la tarea solicitada.
   - Detectar cambios no relacionados y excluirlos del commit.
2. Verificacion tecnica local:
   - Ejecutar lint y/o typecheck del area afectada.
   - Ejecutar pruebas del area afectada (o el set minimo equivalente).
3. Revision de seguridad de cambios:
   - Verificar que no se incluyan secretos, credenciales ni datos sensibles.
   - Confirmar que no se tocaron rutas protegidas sin autorizacion explicita.
4. Actualizacion del banco de memoria:
   - Actualizar memory-bank/progress.md con resumen breve del avance real.
   - Si aplica, ajustar memory-bank/CONTEXT.md con decisiones nuevas.
5. Preparacion de commit:
   - Revisar diff final y redactar mensaje de commit claro y especifico.
   - Verificar que el estado del arbol sea consistente con el alcance acordado.
6. Commit:
   - Crear commit solo cuando los pasos 1-5 esten completos y sin bloqueos.

## Rutas protegidas: no modificar sin confirmacion explicita del desarrollador

El agente no debe modificar las siguientes rutas sin confirmacion explicita:

- memory-bank/
- data/
- docs/
- agents/_template/
- skills/_template/
- apps/talent-pipeline-tracker/AGENTS.md
- apps/talent-pipeline-tracker/CLAUDE.md
- README.md
- README.es.md
- package-lock.json

Si la tarea requiere cambios en alguna ruta protegida, el agente debe pausar y pedir confirmacion antes de editar.
