# Metodologia y resultados para la memoria del TFG

## 1. Planteamiento del problema

Este TFG aborda la recomendacion de zonas residenciales en Madrid como un problema de decision multiobjetivo. El objetivo no es predecir solo precio, sino equilibrar dos criterios en tension:

- Criterio economico: minimizar el precio medio de compra.
- Criterio de accesibilidad: minimizar el tiempo de desplazamiento a destinos relevantes de trabajo o estudio.

Por tanto, la salida del sistema no es una prediccion unica, sino un conjunto de zonas eficientes (frontera de Pareto) y una recomendacion personalizada por perfil de usuario.

## 2. Datos utilizados

### 2.1 Datos inmobiliarios por zona

Se parte del dataset agregado por zone_key (data/datos_zone_ml.csv), con variables como:

- precio_media y precio_m2_media
- metros_media y habitaciones_media
- ascensor_ratio y exterior_ratio

Estas variables capturan coste, tamano y calidad media de vivienda por zona.

### 2.2 Datos de accesibilidad

Se construye una capa de tiempos de viaje por zona y destino (data/accessibility_template.csv), con estructura:

- zone_key
- destino (sol, cuatro_caminos, las_tablas)
- modo
- tiempo_transporte_min
- fuente

Los tiempos se estiman con OpenRouteService y quedan trazados en la columna fuente para asegurar reproducibilidad del experimento.

## 3. Arquitectura metodologica

### 3.1 Integracion de capas

Primero se realiza un merge por zone_key entre los datos inmobiliarios y los tiempos de viaje. La tabla resultante incorpora variables tt_<destino>, por ejemplo tt_sol o tt_las_tablas.

### 3.2 Optimizacion multiobjetivo

Se calcula la frontera de Pareto minimizando simultaneamente:

- precio_media
- tiempo de desplazamiento a destino objetivo

Una zona A domina a B si no es peor en precio y tiempo, y mejora al menos en uno de los dos criterios. Las zonas no dominadas se consideran soluciones eficientes.

### 3.3 Recomendacion personalizada por utilidad

Sobre la tabla integrada se define una funcion de utilidad ponderada por perfil, que combina:

- Penalizacion por precio relativo al presupuesto.
- Penalizacion por tiempo relativo al objetivo de viaje.
- Recompensa por metros y atributos de calidad (exterior, ascensor).

Esto permite generar ranking top-N adaptado a cada persona.

### 3.4 Recomendacion hibrida

El sistema final combina:

- KNN para recuperar zonas similares a las preferencias declaradas.
- Reordenacion por utilidad para imponer el trade-off precio-tiempo.

De esta forma, KNN no actua como objetivo principal, sino como filtro de similitud dentro de una decision multicriterio.

## 4. Validacion por perfiles (personas)

Se plantean tres perfiles representativos:

- Estudiante con presupuesto bajo y destino en centro.
- Profesional con presupuesto alto y prioridad de espacio.
- Familia que busca equilibrio entre coste, tamano y accesibilidad.

Para cada perfil se reporta:

- Top zonas recomendadas.
- Cumplimiento de restricciones (presupuesto y tiempo objetivo).
- Posicion de las zonas en la frontera de Pareto.

Esta validacion demuestra que el sistema se adapta a objetivos distintos y no ofrece una recomendacion unica para todos.

## 5. Indicadores de resultado sugeridos

- Numero de zonas en frontera de Pareto por destino.
- Tiempo medio y precio medio de las zonas eficientes.
- Porcentaje de recomendaciones dentro de presupuesto y tiempo objetivo.
- Analisis de sensibilidad de pesos (cambio de ranking al variar w_tiempo y w_precio).

## 6. Limitaciones y mejoras

Limitaciones actuales:

- Los tiempos de ORS para transporte_publico se usan como proxy de movilidad si no hay GTFS integrado.
- La agregacion por zona oculta heterogeneidad intrazona.

Mejoras futuras:

- Integrar GTFS del Consorcio para tiempos de transporte publico puerta a puerta.
- Contrastar con EDM para calibracion empirica por distrito.
- Incluir variables contextuales (renta, equipamientos, seguridad) para enriquecer la utilidad.

## 7. Contribucion del TFG

La contribucion principal es transformar un enfoque de modelado predictivo clasico en un sistema de recomendacion orientado a decision, con:

- Integracion de datos inmobiliarios y de movilidad.
- Formulacion explicita de trade-off mediante Pareto.
- Personalizacion interpretable por perfiles de usuario.
- Propuesta hibrida (similitud + utilidad) reproducible y extensible.
