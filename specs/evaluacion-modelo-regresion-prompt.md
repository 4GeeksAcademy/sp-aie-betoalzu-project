# Prompt - Evaluacion temporal del modelo de prediccion de ventas

## Objetivo

Completar la evaluacion del pronostico mensual de ingresos de Nexova con validacion cruzada temporal, curva de aprendizaje, metricas de regresion y un diagnostico respaldado por evidencia. La evaluacion debe imitar el uso real del pronostico, evitar fuga de informacion y conservar intacta la comprobacion final fuera de muestra.

## Contexto y fuentes de verdad

- Implementacion existente: `scripts/sales_forecast.py`.
- Pruebas existentes: `tests/pipelines/test_sales_forecast.py`.
- Dataset: `data/raw/nexova_sales.csv`.
- Contexto empresarial disponible: `memory-bank/CONTEXT.md`. No existe un archivo `CONTEXT-empresa.md`; no inventar ni atribuir requisitos a un documento ausente.
- Contexto del modelo y resultados previos: `audit/sales_forecast_report.md`.
- La serie objetivo es la fila mensual consolidada: `business_line == "consolidated"`, fecha `month` e ingreso `revenue_usd` en USD. La serie cubre enero de 2016 a diciembre de 2025.
- El split vigente reserva enero de 2016-diciembre de 2023 para desarrollo y enero de 2024-diciembre de 2025 como holdout final. Mantener esta reserva intacta: no entrenar, seleccionar parametros ni tomar decisiones a partir de sus resultados.
- El modelo fijado por la tarea existente es `RandomForestRegressor`; no sustituirlo ni convertir esta tarea en una comparacion de modelos.

## Alcance de cambios

1. Revisar el codigo y pruebas actuales antes de implementar; preservar sus interfaces y el comportamiento del pronostico recursivo final salvo que sea imprescindible para corregir un defecto de evaluacion.
2. Incorporar la evaluacion en el modulo apropiado siguiendo las convenciones existentes. Evitar duplicar el pipeline de preparacion de datos o alterar el dataset.
3. Anadir una prueba focalizada en `tests/pipelines/` para el orden temporal de folds y, si se introduce una funcion de construccion de folds, probarla directamente.
4. Generar la curva y el informe solo con autorizacion explicita para modificar `data/`: `AGENTS.md` declara esa ruta protegida. Si no se ha concedido, no escribir ni modificar ningun archivo bajo `data/`; dejar documentados en el resultado los artefactos pendientes y pedir autorizacion antes de generarlos.

## Validacion cruzada temporal

- Aplicar al menos 5 folds cronologicos exclusivamente dentro del periodo de entrenamiento 2016-2023. Usar una estrategia expanding-window, sin `shuffle`, como `TimeSeriesSplit`.
- Alinear cada indice de fold con su mes objetivo y comprobar que las fechas son estrictamente crecientes, que el entrenamiento precede a la validacion y que no hay interseccion entre ambos conjuntos. Los indices de validacion de folds sucesivos tambien deben avanzar; ninguno puede retroceder a meses anteriores.
- Para que los resultados representen el pronostico ya implementado, preferir bloques de validacion de 12 meses pronosticados recursivamente. Cada fold entrena el Random Forest solo con los datos anteriores al origen y predice sus 12 meses sin consultar ingresos reales de esos meses; las predicciones generadas se incorporan al historial para los siguientes pasos del mismo bloque. Asegurar que cada origen tenga historia suficiente para los rezagos de 12 meses y datos de entrenamiento suficientes para ajustar el modelo.
- Si la cantidad de observaciones utiles impide usar el tamano de bloque recomendado, ajustar el diseno de forma justificada, manteniendo al menos 5 folds, orden cronologico y una simulacion sin acceso a objetivos futuros. Documentar fechas e intervalos exactos por fold.
- No usar particiones aleatorias, K-fold convencional ni ajustar hiperparametros con el holdout 2024-2025.

## Fuga de informacion en features

- Conservar los nombres y definiciones de dominio existentes: `month`, `recent_vs_year`, objetivo de crecimiento interanual calculado a partir de `revenue_usd`; conservar el filtro de serie consolidada.
- Revisar la causalidad de cada predictor: para el mes objetivo solo puede incluir informacion que estaria disponible antes de ese mes. No incluir `revenue_usd` del propio mes objetivo ni campos contemporaneos como `active_contracts` o `avg_contract_value_usd` si no se puede demostrar que estaban disponibles antes del pronostico.
- Ajustar modelo, imputadores, escaladores, seleccion de variables u otras transformaciones aprendibles usando solo el segmento de entrenamiento de cada fold.
- Los lags y ventanas moviles deben calcularse causalmente y reproducirse igual en validacion que en produccion. No permitir que un predictor de un mes use el objetivo de ese mismo mes o meses posteriores.
- Al construir ventanas para una prediccion, se permite usar observaciones anteriores al origen del fold porque son conocidas en ese momento; durante la validacion recursiva, las ventas reales del bloque de validacion no se pueden agregar al historial. Usar solo historial previo mas predicciones anteriores del propio bloque. No reiniciar arbitrariamente las ventanas en el limite del fold si eso elimina historia que estaria disponible en produccion.
- Anadir comprobaciones de regresion que demuestren que modificar valores posteriores al origen no cambia los features, targets de entrenamiento ni las predicciones anteriores al cambio. Comprobar tambien que los features de cada fecha no consultan datos futuros.

## Metricas y resumen

- Calcular **MAE** y **RMSE** para entrenamiento y validacion en cada fold, siempre expresadas en USD/mes en la escala de ingresos pronosticados. Si el modelo se ajusta sobre crecimiento interanual, convertir primero las predicciones a ingresos siguiendo la logica recursiva de `forecast` antes de medir errores de ingresos.
- Reportar las metricas de validacion entre folds como media ± desviacion estandar muestral (`ddof=1`), por separado para MAE y RMSE; incluir tambien resultados por fold, su periodo y cantidad de meses. No reemplazar esta dispersion por una sola metrica agregada.
- Comparar MAE y RMSE y justificar la metrica principal desde la necesidad de Finanzas: MAE comunica el error absoluto tipico mensual directamente en USD; RMSE da peso adicional a errores grandes y debe mantenerse como indicador complementario del riesgo de desviaciones severas. Si se elige RMSE como principal, justificar por que el costo de errores excepcionalmente grandes domina la decision. No afirmar una asimetria entre sobrestimacion y subestimacion sin evidencia del negocio.
- Mantener cualquier evaluacion final del holdout claramente separada de la validacion cruzada. No combinar meses del holdout con folds ni seleccionar el diagnostico para optimizar los resultados del holdout.

## Curva de aprendizaje

- Crear una curva que muestre error de entrenamiento y error de validacion frente al numero de observaciones temporales de entrenamiento.
- La construccion debe respetar el tiempo: entrenar con prefijos cronologicos y evaluar en periodos posteriores, sin barajar ni reutilizar informacion futura. No usar la curva de aprendizaje aleatoria por defecto de scikit-learn.
- Mostrar unidades y leyenda comprensibles. Incluir MAE y RMSE si la grafica sigue siendo legible; en caso contrario, graficar la metrica principal y presentar la secundaria en el informe.
- Destino requerido: `data/eval/sales_forecast_learning_curve.png`. Por ser una ruta protegida, generar el archivo unicamente tras obtener autorizacion explicita conforme a `AGENTS.md`.

## Informe tecnico

Crear `data/eval/evaluation_report.md` solo tras la autorizacion indicada para `data/`. Debe incluir:

1. Alcance, fuente de datos, campos y filtro de dominio usados, modelo y definicion del holdout que se mantuvo fuera de la validacion cruzada.
2. Metodologia temporal, fechas de origen y validacion por fold, procedimiento recursivo y medidas contra fuga.
3. Tabla de MAE y RMSE de entrenamiento y validacion por fold, junto con media ± desviacion estandar de validacion.
4. La curva de aprendizaje y una interpretacion explicita, clasificada como **bien ajustado**, **underfitting** u **overfitting**. Justificar la clasificacion con la brecha entrenamiento-validacion, la evolucion de los errores al crecer el entrenamiento y la variabilidad entre folds; no inferirla solo de un fold ni de la metrica del holdout.
5. Comparacion de MAE/RMSE y justificacion de la metrica principal en los terminos de costo de negocio descritos arriba.
6. Una accion correctiva concreta, condicionada a la evidencia observada. Por ejemplo, si hay brecha persistente, reducir la varianza del bosque mediante hojas mas grandes o menor profundidad y reevaluar solo con los folds internos; si entrenamiento y validacion tienen error alto y cercano, investigar primero si las features causales disponibles capturan los cambios de ingresos antes de aumentar capacidad. No cambiar hiperparametros basandose en el holdout ni recomendar generically agregar datos o complejidad.
7. Limitaciones, cualquier desviacion del diseno y comandos reproducibles para ejecutar pruebas y evaluacion.

No inventar resultados, diagnosticos o justificaciones empresariales. Si la evidencia no permite separar con confianza las tres categorias, explicar la ambiguedad y la evidencia insuficiente en vez de presentar una certeza falsa.

## Prueba requerida

En `tests/pipelines/`, validar como minimo que:

- todos los indices de entrenamiento de cada fold preceden a sus indices de validacion;
- las fechas dentro de cada particion estan en orden creciente;
- las validaciones de folds sucesivos avanzan en el tiempo y no vuelven a indices anteriores;
- entrenamiento y validacion no se solapan y no hay barajado.

Anadir aserciones para la causalidad de features/validacion recursiva si se crea una funcion que permita probarlo sin depender de archivos generados.

## Criterios de aceptacion

- Hay al menos 5 folds de origen temporal, sin mezcla ni barajado, definidos sobre el entrenamiento y con el holdout final intacto.
- La evaluacion refleja pronosticos recursivos y no incorpora ventas reales del bloque que se esta pronosticando.
- Se demuestra que los features son causales y que transformaciones aprendibles se ajustan dentro de cada fold.
- Se calculan MAE y RMSE de entrenamiento y validacion; se reportan resultados por fold y media ± desviacion estandar muestral de validacion.
- La curva de aprendizaje usa cortes temporales y se guarda en la ruta especificada tras autorizacion.
- El informe contiene diagnostico explicito y evidencia, una justificacion de negocio para la metrica principal y una accion correctiva especifica y coherente.
- Las pruebas focalizadas de `tests/pipelines/` pasan.
