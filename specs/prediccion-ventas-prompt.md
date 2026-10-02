# Prompt — Modelo de predicción de ventas

## Objetivo

Entrenar un modelo de predicción de ventas para los próximos meses con un enfoque riguroso y honesto. **La elección del algoritmo no forma parte de esta tarea: el desarrollador decidirá qué modelo usar y lo indicará explícitamente.** El agente se encarga de limpiar los datos, aplicar la separación temporal indicada, entrenar el modelo elegido, evaluarlo sobre datos no vistos y visualizar los resultados de forma comprensible para Finanzas.

## Modelo a utilizar

- Modelo: **Random Forest** (`sklearn.ensemble.RandomForestRegressor`)
- El agente **no debe** elegir, comparar ni sustituir el modelo por su cuenta.
- El script de entrenamiento debe incluir, junto a la instanciación del modelo, un comentario breve que justifique por qué se eligió Random Forest para este problema. Como mínimo debe mencionar:
  - robustez con pocos datos (~84 filas útiles tras los lags de 12 meses) y menor riesgo de overfitting que el boosting,
  - buen rendimiento con hiperparámetros casi por defecto, ya que el tuning solo puede hacerse dentro del periodo de entrenamiento,
  - intervalo de incertidumbre obtenible de forma nativa a partir de la dispersión entre árboles,
  - patrón estacional simple que no requiere la capacidad extra de XGBoost,
  - limitación conocida: no extrapola la tendencia, por lo que el target debe modelarse como crecimiento interanual.

## Datos y contexto

- Dataset: `data/raw/nexova_sales.csv`.
- Contexto del dataset (esquema, patrones y restricciones): `agent-train.md`. Leerlo antes de preparar los datos.

## Contexto del negocio

Finanzas quiere saber si es viable predecir las ventas de los próximos meses a partir del histórico disponible. Antes de prometernos una capacidad predictiva, se requiere validar la calidad del modelo con evidencia real y una evaluación transparente.

La entrega debe ser útil para una conversación ejecutiva: debe mostrar si el modelo puede aproximar mejor que una simple tendencia, cuánta incertidumbre tiene la predicción y qué tipo de error se está cometiendo en unidades de negocio reales.

## Requisitos no negociables

1. Dividir el dataset en dos periodos temporales:
   - Entrenamiento: primeros 8 años de datos disponibles.
   - Validación/predicción: los 2 años más recientes, que el modelo no debe haber visto durante el entrenamiento.
2. No usar los 2 años recientes para ajustar hiperparámetros ni recalibrar el modelo.
3. La salida final debe incluir una visualización con:
   - serie histórica real,
   - predicción del modelo,
   - intervalo de variabilidad o rango de incertidumbre,
   - marcado del periodo de validación no visto por el modelo.
4. Usar únicamente el modelo indicado por el desarrollador.
5. La métrica de error debe ser interpretable para negocio y no solo una puntuación abstracta.
6. Se debe incluir una conclusión honesta sobre la confianza del modelo y sus limitaciones.

## Tarea a ejecutar

Revisa el conjunto de datos de ventas disponible en el repositorio, identifica la serie temporal relevante y prepara el análisis para responder esta pregunta:

- ¿Podemos predecir las ventas futuras con suficiente fiabilidad para que Finanzas tome decisiones con un margen de riesgo conocido?

## Instrucciones para la ejecución

### 1) Carga y preparación de datos

- Revisar el dataset histórico de ventas y detectar el nivel temporal correcto (mensual, trimestral o diario, según corresponda).
- Validar la presencia de fechas, ventas y posibles valores faltantes, outliers o cambios estructurales.
- Preparar una versión limpia para modelado temporal, manteniendo la integridad de la serie.
- Si hay variables explicativas relevantes (temporada, promociones, campañas, días festivos, tendencias, etc.), incorporarlas solo si tienen sentido y están disponibles en el histórico.
- Documentar qué variables se usaron y cuáles se descartaron por falta de valor o por riesgo de leakage.

### 2) Separación temporal y evaluación honesta

- Usar exactamente los primeros 8 años para entrenamiento.
- Mantener los 2 años más recientes como conjunto de comprobación fuera de muestra.
- Confirmar que la separación temporal es estricta y que los datos de validación no forman parte del entrenamiento.
- Evaluar el modelo únicamente sobre ese periodo reciente no visto.
- No presentar resultados de entrenamiento como si fueran resultados de validación.

### 3) Entrenamiento del modelo indicado

- Entrenar exclusivamente el modelo indicado por el desarrollador, usando solo el periodo de entrenamiento (8 años).
- Si se ajustan hiperparámetros, hacerlo solo con validación temporal dentro del periodo de entrenamiento (p. ej. `TimeSeriesSplit`), nunca con los 2 años recientes.
- Generar predicciones para el periodo de validación.
- Incluir una línea base simple (p. ej. naive estacional o tendencia) solo como referencia para saber si el modelo aporta valor; no es una comparación de modelos candidatos.

### 4) Métrica de error explicable para Finanzas

Usar una métrica de error que pueda explicarse en unidades de negocio, no solo como un score técnico. La más recomendada es:
- MAE (Mean Absolute Error) o Error Medio Absoluto

También puede incluirse una segunda métrica auxiliar si aporta contexto adicional, por ejemplo:
- RMSE
- MAPE (solo si el volumen no es cercano a cero y se interpreta con cuidado)

La explicación debe ser clara para no expertos: por ejemplo, "el modelo se equivoca en promedio X € por mes" o "el error medio en ventas mensuales es de Y unidades".

### 5) Visualización requerida

Generar una visualización que muestre claramente:
- la serie histórica real,
- la predicción del modelo,
- el rango de variabilidad o intervalo de incertidumbre,
- el punto de corte entre entrenamiento y validación.

La visualización debe tener un formato profesional y ejecutable, y no debe limitarse a un único número optimista. Debe reflejar la incertidumbre de la predicción para que Finanzas comprenda que no hay una sola proyección exacta.

### 6) Conclusión y riesgo

La respuesta final debe contener:
- cómo se comportó el modelo indicado en validación frente a la línea base,
- cuánto error hubo en la predicción reciente,
- si la precisión es suficiente para apoyar decisiones de negocio,
- qué riesgos quedan: estacionalidad, cambios estructurales, demanda atípica, campañas, promociones, outliers, etc.,
- si el modelo es útil para planificación o si requiere más señales y refinamiento.

## Salida esperada

La entrega debe ser una revisión metodológica y analítica con resultados concretos, escrita de forma clara para un stakeholder de negocio y con una base técnica sólida. Debe incluir:

- resumen ejecutivo,
- preparación de datos,
- separación temporal,
- entrenamiento del modelo indicado,
- métrica de error interpretada para negocio,
- gráfica de predicción con rango de variabilidad,
- conclusión honesta sobre capacidad predictiva y limitaciones.

## Criterios de aceptación

Se considera correcta la tarea si:

- la validación se hace con los 2 años más recientes no vistos,
- se entrena únicamente el modelo indicado por el desarrollador,
- el script incluye un comentario que justifica la elección de Random Forest,
- se muestra una predicción con intervalo de incertidumbre,
- se reporta un error interpretable para Finanzas,
- no se exagera la precisión ni se oculta la incertidumbre.

## Importante

No se trata de "hacer que el modelo parezca mejor" ni de ajustar el conjunto de validación para obtener un resultado más favorable. Se prioriza la honestidad técnica y la utilidad para la toma de decisiones. Si el modelo no es suficientemente fiable, debe decirse claramente, con la evidencia detrás de esa conclusión.
