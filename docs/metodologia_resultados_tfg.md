# Metodología y resultados del TFG

## 1. Planteamiento del problema

Este Trabajo de Fin de Grado plantea el desarrollo de un sistema de recomendación de barrios residenciales en Madrid.

El objetivo del sistema no es únicamente estimar el precio de una vivienda, sino ayudar al usuario a identificar los barrios que mejor se adaptan a sus necesidades personales, económicas y de movilidad.

La elección de una zona residencial constituye un problema de decisión multicriterio, ya que intervienen factores que pueden entrar en conflicto. Por ejemplo, los barrios con precios más reducidos pueden presentar mayores tiempos de desplazamiento, mientras que los barrios mejor comunicados pueden superar el presupuesto disponible.

Por tanto, el sistema debe considerar simultáneamente criterios como:

* Precio representativo de la vivienda.
* Presupuesto máximo del usuario.
* Tiempo de desplazamiento hasta un destino habitual.
* Superficie de la vivienda.
* Número de habitaciones.
* Disponibilidad de ascensor.
* Carácter exterior o interior de las viviendas.
* Fiabilidad de los datos disponibles.
* Preferencias y restricciones particulares del usuario.

La salida del sistema no consistirá en una única zona universalmente óptima, sino en un conjunto ordenado de barrios adecuados para cada perfil de usuario, acompañado de una explicación de los motivos de la recomendación.

---

## 2. Unidad territorial de análisis

La unidad territorial definitiva del proyecto es el **barrio oficial del municipio de Madrid**.

Madrid está dividido administrativamente en:

* 21 distritos.
* 131 barrios oficiales.

Cada fila del dataset inmobiliario agregado representa un barrio oficial.

El distrito se conserva como atributo territorial superior, pero no se mezcla con los barrios como si ambos fueran unidades equivalentes.

La estructura territorial utilizada es:

```text
Madrid
    ↓
Distrito
    ↓
Barrio
```

Esta decisión permite:

* Trabajar con una granularidad suficientemente detallada.
* Comparar zonas residenciales concretas.
* Evitar la mezcla de distritos, barrios y denominaciones comerciales.
* Integrar posteriormente datos oficiales y de movilidad.
* Mantener una correspondencia territorial estable mediante un identificador único.

Cada barrio se identifica mediante la variable:

```text
zone_key
```

Además, se conservan:

* Código del distrito.
* Nombre del distrito.
* Código del barrio.
* Nombre del barrio.
* Latitud representativa.
* Longitud representativa.
* Superficie aproximada.

---

## 3. Fuentes de datos

### 3.1. Datos inmobiliarios

El dataset inmobiliario inicial procede de Kaggle, concretamente del conjunto:

* **Nombre:** Idealista MADRID.
* **Autor en Kaggle:** `fjcob1`.
* **Plataforma:** Kaggle.
* **Contenido:** anuncios de viviendas en venta publicados en Idealista en Madrid.

El archivo original se conserva en:

```text
data/raw/historical/idealista_listings_unknown_date.csv
```

Entre sus campos originales se encuentran:

* Provincia.
* Zona.
* Título del anuncio.
* Precio actual.
* Precio anterior.
* Superficie.
* Número de habitaciones.
* Número de baños.
* Ascensor.
* Localización.
* Planta.
* Etiquetas.
* Descripción.
* Enlace.

El dataset contiene precios de oferta publicados en anuncios inmobiliarios. Estos valores no equivalen necesariamente a los precios finales de compraventa.

La fecha exacta de recopilación no ha podido determinarse, por lo que el conjunto se considera una muestra histórica de la oferta inmobiliaria.

Esta limitación se tendrá en cuenta durante la interpretación de los resultados y, cuando sea posible, los precios agregados se contrastarán con otra fuente inmobiliaria u oficial.

### 3.2. División territorial oficial

La estructura de barrios procede de la cartografía oficial de barrios municipales publicada por el Ayuntamiento de Madrid.

Los archivos territoriales originales se almacenan en:

```text
data/raw/official/
```

A partir de esta información se genera:

```text
data/processed/zones_master.csv
data/processed/zones_master.geojson
```

`zones_master.csv` contiene una fila para cada uno de los 131 barrios oficiales y constituye la tabla maestra territorial del proyecto.

### 3.3. Datos de movilidad

La capa de movilidad todavía se encuentra pendiente de implementación definitiva.

El transporte público real es un requisito obligatorio del sistema.

La fuente seleccionada deberá permitir calcular tiempos que contemplen, en la medida de lo posible:

* Recorrido a pie hasta la parada.
* Metro.
* Autobús.
* Cercanías.
* Tiempos de espera.
* Transbordos.
* Recorrido final a pie.
* Fecha y hora del desplazamiento.

Los tiempos en coche, bicicleta y andando podrán incorporarse como variables complementarias, pero no se utilizará el tiempo en coche como sustituto del transporte público.

---

## 4. Arquitectura general del procesamiento

El pipeline del proyecto se divide en las siguientes fases:

```text
Datos inmobiliarios originales
        ↓
Auditoría inicial
        ↓
Construcción de la estructura territorial
        ↓
Asignación de anuncios a barrios oficiales
        ↓
Limpieza de precios y características
        ↓
Detección de anuncios no representativos
        ↓
Selección de anuncios válidos
        ↓
Agregación inmobiliaria por barrio
        ↓
Cálculo de tiempos de desplazamiento
        ↓
Construcción del dataset maestro
        ↓
Sistema de recomendación
        ↓
Evaluación de resultados
```

Las fases inmobiliarias están implementadas hasta la agregación por barrios. Las fases de transporte y recomendación se desarrollarán posteriormente.

---

## 5. Auditoría inicial del dataset inmobiliario

La primera fase consiste en analizar el dataset original antes de realizar transformaciones.

El objetivo de esta auditoría es conocer:

* Número de filas y columnas.
* Tipos de datos.
* Valores ausentes.
* Posibles duplicados.
* Variables disponibles.
* Distribución territorial.
* Formatos utilizados.
* Problemas de calidad.
* Coherencia de los precios y superficies.

El dataset original contiene 11.826 anuncios inmobiliarios.

También se comprueba la unicidad de los enlaces y la existencia de valores anómalos en columnas como:

* Precio.
* Superficie.
* Habitaciones.
* Baños.
* Planta.
* Localización.

Esta fase se implementa en:

```text
notebooks/01_auditoria_datos.ipynb
```

---

## 6. Construcción y validación territorial

El dataset original contiene denominaciones territoriales utilizadas por el portal inmobiliario.

Estas denominaciones no siempre coinciden directamente con los barrios administrativos oficiales. Algunas corresponden a:

* Distritos.
* Barrios.
* Subzonas inmobiliarias.
* Denominaciones populares.
* Áreas que incluyen más de un barrio.

Por este motivo, se construye una correspondencia entre las localizaciones del dataset inmobiliario y los 131 barrios oficiales.

El proceso incluye:

1. Lectura de la cartografía oficial.
2. Construcción de la tabla territorial maestra.
3. Generación de un identificador `zone_key`.
4. Obtención de un punto representativo para cada barrio.
5. Extracción y normalización de las denominaciones inmobiliarias.
6. Correspondencia automática cuando la relación es inequívoca.
7. Revisión de los casos dudosos.
8. Validación de que los anuncios quedan asociados a barrios existentes.

La asignación territorial permite transformar datos cuya localización inicial era heterogénea en un dataset estructurado por barrios oficiales.

Esta fase se implementa en:

```text
notebooks/02_validacion_zonas.ipynb
```

Su resultado territorial principal es:

```text
data/processed/zones_master.csv
```

---

## 7. Limpieza de anuncios inmobiliarios

La tercera fase transforma los anuncios originales en registros adecuados para el análisis inmobiliario.

Esta fase se implementa en:

```text
notebooks/03_limpieza_anuncios.ipynb
```

### 7.1. Limpieza del precio

Los valores de precio se convierten a formato numérico.

Se eliminan o gestionan:

* Símbolos monetarios.
* Separadores de miles.
* Espacios.
* Valores vacíos.
* Formatos incompatibles.

Se conserva el precio total anunciado y se calcula el precio por metro cuadrado:

```text
precio_m2 = precio_total / superficie
```

El precio por metro cuadrado permite comparar viviendas de diferentes tamaños.

### 7.2. Limpieza de superficie

La superficie se convierte a una variable numérica expresada en metros cuadrados.

Se revisan:

* Valores ausentes.
* Valores incompatibles.
* Superficies extremadamente pequeñas o grandes.
* Posibles errores de formato.

### 7.3. Habitaciones y baños

El número de habitaciones se transforma a formato numérico.

El número de baños se recupera cuando está disponible de forma estructurada o puede extraerse con suficiente fiabilidad del texto del anuncio.

No obstante, la cobertura del número de baños es limitada. Por este motivo, esta variable no se utilizará inicialmente como uno de los criterios principales del recomendador.

### 7.4. Ascensor

La información de ascensor se normaliza mediante una variable binaria o categórica.

Se distingue entre:

* Vivienda con ascensor.
* Vivienda sin ascensor.
* Información desconocida.

Los valores desconocidos no se convierten automáticamente en ausencia de ascensor.

### 7.5. Vivienda exterior

Se identifica si la vivienda se anuncia como exterior o interior.

También en este caso se conserva la diferencia entre:

* Exterior.
* Interior.
* Desconocido.

### 7.6. Planta

La planta del inmueble se limpia y normaliza.

Se contemplan casos como:

* Bajo.
* Primera planta.
* Plantas intermedias.
* Ático.
* Desconocido.

### 7.7. Tipo de inmueble

Se revisa el tipo de inmueble con el objetivo de excluir registros que no representen viviendas residenciales comparables.

Pueden aparecer:

* Pisos.
* Apartamentos.
* Chalés.
* Casas.
* Estudios.
* Locales.
* Garajes.
* Terrenos.
* Otros inmuebles no residenciales.

### 7.8. Operaciones especiales

Algunos anuncios presentan precios que no representan una compraventa residencial convencional.

Entre ellos se encuentran:

* Viviendas ocupadas.
* Venta sin posesión.
* Nuda propiedad.
* Usufructo.
* Proindivisos.
* Venta de participaciones.
* Subastas.
* Viviendas vendidas con inquilino.
* Cesiones o situaciones jurídicas especiales.

Estos anuncios pueden presentar precios artificialmente reducidos y alterar las estadísticas de un barrio.

Por ello se identifican mediante:

* Título.
* Descripción.
* Etiquetas.
* Expresiones características.
* Revisión manual de los casos dudosos.

Las decisiones manuales relevantes se conservan en un archivo de validación para asegurar la trazabilidad del proceso.

### 7.9. Duplicados

Se analiza la posible existencia de anuncios duplicados utilizando:

* Enlace.
* Precio.
* Superficie.
* Habitaciones.
* Localización.
* Título.
* Descripción.
* Combinaciones de características.

No todos los anuncios similares son necesariamente duplicados, por lo que los casos dudosos deben analizarse antes de eliminarlos.

### 7.10. Selección de anuncios válidos

Después de aplicar las reglas de limpieza se generan dos archivos principales:

```text
data/processed/listings_clean.csv
data/processed/listings_market_eligible.csv
```

`listings_clean.csv` contiene los anuncios tras la limpieza y normalización.

`listings_market_eligible.csv` contiene los anuncios considerados aptos para representar el mercado residencial convencional.

De los 11.826 anuncios originales, 11.109 se consideran utilizables para la agregación inmobiliaria.

---

## 8. Agregación inmobiliaria por barrio

La cuarta fase convierte los anuncios individuales en una caracterización agregada de cada barrio.

Esta fase se implementa en:

```text
notebooks/04_agregacion_barrios.ipynb
```

Cada fila del resultado representa uno de los 131 barrios oficiales.

### 8.1. Variables de precio

Se calculan:

* Número de anuncios.
* Precio total medio.
* Precio total mediano.
* Precio por metro cuadrado medio.
* Precio por metro cuadrado mediano.
* Desviación estándar.
* Primer cuartil.
* Tercer cuartil.
* Intervalo intercuartílico.
* Valores mínimos y máximos cuando resulten útiles.

La mediana se utiliza como medida principal porque es menos sensible que la media a viviendas extremadamente caras o baratas.

### 8.2. Variables de tamaño

Se calculan:

* Superficie media.
* Superficie mediana.
* Número medio de habitaciones.
* Número mediano de habitaciones.
* Número medio y mediano de baños cuando existe cobertura suficiente.

### 8.3. Características de las viviendas

Se calculan proporciones como:

* Porcentaje de viviendas con ascensor.
* Porcentaje de viviendas exteriores.
* Cobertura conocida de cada atributo.

Las proporciones se calculan únicamente sobre los registros con información conocida, evitando interpretar los valores ausentes como respuestas negativas.

### 8.4. Cobertura territorial

Se genera una auditoría para conocer:

* Barrios con anuncios.
* Barrios sin anuncios.
* Número de anuncios por barrio.
* Cobertura de las variables.
* Barrios con muestras reducidas.

Actualmente, 129 de los 131 barrios presentan información inmobiliaria.

Los barrios sin anuncios válidos son:

* Atocha.
* Valdebernardo.

Estos barrios se conservan en el dataset territorial, pero sus precios no se sustituyen por cero.

### 8.5. Incertidumbre y fiabilidad

El número de anuncios varía considerablemente entre barrios.

Por tanto, una estimación basada en cientos de anuncios no debe tratarse igual que una estimación basada en dos o tres registros.

Para representar esta diferencia se calculan variables como:

```text
num_listings
price_m2_median
price_m2_median_ci_low
price_m2_median_ci_high
price_m2_median_ci_width
price_reliability_score
price_reliability_level
price_reliability_reason
```

La puntuación de fiabilidad considera factores como:

* Tamaño de la muestra.
* Anchura del intervalo de confianza.
* Dispersión interna.
* Existencia o ausencia de datos.

La clasificación actual distingue entre:

* Fiabilidad alta.
* Fiabilidad media.
* Fiabilidad baja.
* Muestra insuficiente.
* Sin datos.

Los resultados principales de la agregación son:

```text
data/processed/neighborhood_coverage_audit.csv
data/processed/neighborhood_price_uncertainty.csv
data/processed/neighborhood_real_estate_summary.csv
```

---

## 9. Cálculo de los tiempos de desplazamiento

La siguiente fase será la construcción de la capa de accesibilidad.

Se implementará en:

```text
notebooks/05_tiempos_transporte.ipynb
```

### 9.1. Orígenes

Los orígenes serán los puntos representativos de los 131 barrios, almacenados en:

```text
data/processed/zones_master.csv
```

Cada origen tendrá:

* `zone_key`.
* Barrio.
* Distrito.
* Latitud.
* Longitud.

### 9.2. Destinos

Los destinos podrán ser:

* Una dirección proporcionada por el usuario.
* Una universidad.
* Un lugar de trabajo.
* Un nodo de transporte.
* Un punto de referencia utilizado en los experimentos.

### 9.3. Momento del viaje

Los tiempos de transporte público dependen del momento de consulta.

Por ello deberán definirse y almacenarse:

* Fecha.
* Hora.
* Zona horaria.
* Día laborable o festivo.
* Hora punta o valle.

Para los experimentos se seleccionarán momentos de referencia comparables, preferentemente días laborables y franjas horarias representativas.

### 9.4. Modos de transporte

El modo obligatorio será:

* Transporte público real.

Como variables complementarias podrán incluirse:

* Coche.
* Bicicleta.
* Caminando.

### 9.5. Información almacenada

Cada consulta deberá guardar al menos:

```text
zone_key
origin_latitude
origin_longitude
destination_id
destination_latitude
destination_longitude
transport_mode
departure_datetime
duration_minutes
distance_km
number_of_transfers
data_source
request_status
error_message
calculation_timestamp
```

La disponibilidad exacta de algunas variables dependerá de la fuente de rutas seleccionada.

### 9.6. Control de errores

El pipeline deberá contemplar:

* Errores de conexión.
* Límites de uso de la API.
* Barrios sin ruta.
* Destinos no encontrados.
* Respuestas incompletas.
* Reintentos.
* Almacenamiento parcial de resultados.
* Evitar repetir peticiones ya realizadas.

---

## 10. Construcción del dataset maestro

La integración final se realizará en:

```text
notebooks/06_dataset_recomendador.ipynb
```

El dataset maestro combinará:

* Variables territoriales.
* Variables inmobiliarias.
* Variables de fiabilidad.
* Tiempos de desplazamiento.
* Información de los destinos.
* Variables adicionales seleccionadas.

La unión principal se realizará mediante:

```text
zone_key
```

Antes de construir el recomendador se revisarán:

* Duplicados.
* Valores ausentes.
* Tipos de datos.
* Escalas.
* Unidades.
* Cobertura.
* Coherencia territorial.
* Coherencia temporal.

---

## 11. Normalización de variables

Las variables presentan escalas diferentes.

Por ejemplo:

* Precio en euros.
* Precio por metro cuadrado en euros por metro cuadrado.
* Tiempo en minutos.
* Superficie en metros cuadrados.
* Ascensor como proporción.
* Fiabilidad entre 0 y 1.

Para aplicar métodos de distancia como KNN será necesario normalizarlas o estandarizarlas.

La normalización deberá ajustarse únicamente con los datos utilizados para construir el modelo, evitando introducir información de evaluación en la fase de entrenamiento o configuración.

Las variables en las que un valor menor es mejor, como precio o tiempo, deberán tratarse de forma diferente a las variables en las que un valor mayor es preferible, como superficie o fiabilidad.

---

## 12. Sistema de recomendación

El recomendador se implementará en:

```text
notebooks/07_recomendador.ipynb
```

La propuesta combina cuatro componentes:

1. Restricciones obligatorias.
2. Optimización multiobjetivo mediante Pareto.
3. Similitud mediante KNN.
4. Explicación de resultados.

### 12.1. Restricciones obligatorias

Antes de ordenar las alternativas se aplicarán las condiciones que el usuario considere imprescindibles.

Ejemplos:

* Precio máximo.
* Tiempo máximo de desplazamiento.
* Número mínimo de habitaciones.
* Superficie mínima.
* Disponibilidad mínima de ascensor.
* Nivel mínimo de fiabilidad.

Los barrios que incumplan estas restricciones podrán excluirse antes del ranking.

También deberá contemplarse el caso en el que ninguna alternativa cumpla todas las condiciones. En ese supuesto, el sistema deberá informar al usuario y mostrar las alternativas más próximas, indicando qué restricciones se incumplen.

### 12.2. Frontera de Pareto

La frontera de Pareto se utilizará para representar el equilibrio entre objetivos contrapuestos.

Inicialmente se considerarán como objetivos principales:

* Minimizar el precio.
* Minimizar el tiempo de transporte público.

Un barrio A domina a otro barrio B cuando:

* A no es peor que B en ninguno de los objetivos.
* A mejora a B en al menos uno de ellos.

Los barrios no dominados forman la frontera de Pareto.

Este método evita recomendar barrios claramente inferiores a otros tanto en precio como en desplazamiento.

### 12.3. KNN

KNN se utilizará como método de similitud basado en contenido.

El perfil del usuario y cada barrio se representarán mediante variables como:

* Precio.
* Tiempo.
* Superficie.
* Habitaciones.
* Ascensor.
* Exterior.
* Fiabilidad.

Después de normalizar las variables, KNN permitirá identificar los barrios más próximos al perfil solicitado.

En este proyecto KNN no constituye filtrado colaborativo, ya que no se dispone de valoraciones ni interacciones históricas de usuarios.

### 12.4. Sistema híbrido

El sistema final combinará los métodos de la siguiente forma:

```text
Preferencias del usuario
        ↓
Restricciones obligatorias
        ↓
Cálculo de alternativas no dominadas
        ↓
Ordenación por similitud mediante KNN
        ↓
Ajuste por fiabilidad
        ↓
Explicación de recomendaciones
```

Pareto será el componente principal para gestionar el equilibrio entre precio y desplazamiento.

KNN se utilizará para personalizar y ordenar las alternativas según el conjunto completo de preferencias.

### 12.5. Explicabilidad

Cada recomendación deberá acompañarse de una explicación comprensible.

Ejemplo:

> Este barrio se recomienda porque se encuentra dentro del presupuesto indicado, presenta un tiempo de transporte público inferior al máximo establecido y ofrece una superficie mediana próxima a la solicitada. La estimación de precio presenta una fiabilidad media debido al número de anuncios disponibles.

Las explicaciones deberán señalar también:

* Variables especialmente favorables.
* Restricciones cumplidas.
* Restricciones incumplidas.
* Nivel de fiabilidad.
* Relación con otras alternativas.

---

## 13. Perfiles de evaluación

El sistema se evaluará mediante perfiles representativos.

### 13.1. Perfil estudiante

Características posibles:

* Presupuesto reducido.
* Prioridad alta al transporte público.
* Aceptación de menor superficie.
* Destino habitual en una universidad o zona céntrica.

### 13.2. Perfil profesional

Características posibles:

* Presupuesto medio o alto.
* Prioridad alta al tiempo de desplazamiento.
* Preferencia por ascensor.
* Mayor importancia de la superficie.
* Destino habitual en una zona de oficinas.

### 13.3. Perfil familiar

Características posibles:

* Necesidad de varias habitaciones.
* Preferencia por mayor superficie.
* Equilibrio entre precio y desplazamiento.
* Posible incorporación futura de servicios cercanos.

Estos perfiles no pretenden representar a todos los usuarios, sino proporcionar casos de prueba comparables y reproducibles.

---

## 14. Estrategia de evaluación

Se compararán diferentes configuraciones del recomendador:

1. Ranking ponderado.
2. KNN sin Pareto.
3. Pareto sin KNN.
4. Sistema híbrido de filtros, Pareto y KNN.
5. Sistema híbrido con ajuste por fiabilidad.

La evaluación podrá considerar:

* Porcentaje de recomendaciones dentro del presupuesto.
* Porcentaje dentro del tiempo máximo.
* Número de alternativas dominadas recomendadas.
* Distancia respecto al perfil solicitado.
* Diversidad territorial.
* Fiabilidad media de los barrios recomendados.
* Estabilidad ante pequeños cambios en las preferencias.
* Sensibilidad a los pesos.
* Diferencias entre perfiles.
* Capacidad de explicar los resultados.

Debido a la ausencia de valoraciones históricas de usuarios, la evaluación inicial será experimental y basada en escenarios.

Como ampliación, podrán realizarse pruebas con usuarios para analizar:

* Utilidad percibida.
* Coherencia de las recomendaciones.
* Claridad de las explicaciones.
* Facilidad de uso.

---

## 15. Resultados actuales

La fase inmobiliaria produce los siguientes resultados:

| Indicador                            | Resultado |
| ------------------------------------ | --------: |
| Anuncios originales                  |    11.826 |
| Anuncios aptos para el análisis      |    11.109 |
| Distritos oficiales                  |        21 |
| Barrios oficiales                    |       131 |
| Barrios con información inmobiliaria |       129 |
| Barrios sin información inmobiliaria |         2 |
| Barrios con fiabilidad alta          |        19 |
| Barrios con fiabilidad media         |        44 |
| Barrios con fiabilidad baja          |        63 |
| Barrios con muestra insuficiente     |         3 |

Los resultados muestran que la cobertura territorial es elevada, aunque el número de anuncios es desigual entre barrios.

Esta desigualdad justifica la incorporación de métricas de incertidumbre y fiabilidad dentro del recomendador.

---

## 16. Limitaciones actuales

### 16.1. Antigüedad desconocida del dataset

La fecha exacta de recopilación de los anuncios no está identificada.

Por ello, el dataset se considera histórico y deberá interpretarse como una muestra de la oferta de un periodo no determinado.

### 16.2. Precios de oferta

Los precios corresponden a anuncios y no a operaciones finales de compraventa.

### 16.3. Cobertura desigual

Algunos barrios disponen de cientos de anuncios, mientras que otros cuentan con muestras muy reducidas.

### 16.4. Barrios sin anuncios

Atocha y Valdebernardo no disponen actualmente de datos inmobiliarios válidos.

### 16.5. Cobertura de atributos

La cobertura de variables como el número de baños es limitada.

### 16.6. Punto representativo del barrio

Las rutas se calcularán inicialmente desde un punto representativo de cada barrio.

Este punto simplifica el cálculo, pero no representa todas las ubicaciones posibles dentro del barrio.

### 16.7. Dependencia temporal del transporte

Los tiempos de transporte público dependen del día, la hora, las frecuencias y las incidencias.

### 16.8. Ausencia de interacciones de usuarios

No se dispone de un historial real de valoraciones o elecciones residenciales.

Por ello, el recomendador se basará inicialmente en contenido, restricciones y perfiles simulados.

---

## 17. Posibles mejoras

Entre las futuras ampliaciones se encuentran:

* Incorporar una fuente inmobiliaria adicional y más reciente.
* Comparar los precios de oferta con estadísticas oficiales.
* Añadir información de alquiler.
* Calcular rutas desde varios puntos de cada barrio.
* Incorporar más de un destino por usuario.
* Considerar horarios alternativos.
* Añadir equipamientos y servicios.
* Incorporar renta, seguridad o zonas verdes.
* Realizar validación con usuarios.
* Desarrollar una aplicación web.
* Mostrar los resultados en un mapa interactivo.
* Permitir modificar pesos y restricciones.

---

## 18. Contribución del proyecto

La contribución principal del TFG consiste en desarrollar un sistema reproducible de apoyo a la decisión residencial basado en la integración de:

* Datos inmobiliarios.
* División territorial oficial.
* Datos de movilidad.
* Incertidumbre de los precios.
* Restricciones personales.
* Optimización multiobjetivo.
* Similitud basada en contenido.
* Explicaciones de las recomendaciones.

El proyecto no se limita a construir un modelo predictivo, sino que transforma información heterogénea en recomendaciones adaptadas a diferentes necesidades.

La utilización conjunta de filtros, frontera de Pareto, KNN y métricas de fiabilidad permitirá ofrecer alternativas personalizadas, evitar soluciones claramente dominadas y comunicar las limitaciones de los datos utilizados.

---

## 19. Estado actual del desarrollo

### Implementado

* Auditoría del dataset inmobiliario.
* Construcción de la tabla territorial oficial.
* Representación de los 131 barrios.
* Correspondencia entre zonas inmobiliarias y barrios.
* Limpieza de precios y superficies.
* Limpieza de habitaciones y atributos.
* Detección de operaciones especiales.
* Detección de posibles duplicados.
* Selección de anuncios aptos.
* Agregación inmobiliaria por barrio.
* Evaluación de cobertura.
* Estimación de incertidumbre.
* Clasificación de la fiabilidad.

### Pendiente

* Selección de la fuente definitiva de transporte público.
* Obtención de tiempos reales de desplazamiento.
* Integración de las capas inmobiliaria y de movilidad.
* Construcción del dataset maestro.
* Implementación de Pareto.
* Implementación de KNN.
* Construcción del sistema híbrido.
* Evaluación comparativa.
* Generación de explicaciones.
* Posible desarrollo de una interfaz.
