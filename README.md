# Sistema de recomendación de barrios residenciales en Madrid

Trabajo de Fin de Grado centrado en el desarrollo de un sistema de recomendación de barrios residenciales de Madrid mediante la integración de información inmobiliaria, información territorial y tiempos de desplazamiento.

El objetivo del proyecto no es únicamente estimar el precio de una vivienda, sino ayudar al usuario a identificar qué barrios se ajustan mejor a sus necesidades, considerando simultáneamente factores como:

* Presupuesto disponible.
* Precio representativo de la vivienda.
* Tiempo de desplazamiento hasta un destino habitual.
* Superficie y número de habitaciones.
* Presencia de ascensor.
* Carácter exterior o interior de las viviendas.
* Fiabilidad de la información disponible para cada barrio.
* Preferencias específicas del usuario.

El sistema se plantea como un problema de recomendación multicriterio en el que existen objetivos potencialmente contradictorios. Por ejemplo, los barrios con precios más reducidos pueden presentar tiempos de desplazamiento mayores, mientras que los barrios mejor comunicados pueden superar el presupuesto del usuario.

---

## 1. Objetivo del proyecto

El objetivo general es desarrollar un sistema capaz de recomendar barrios oficiales de Madrid a partir de las restricciones y preferencias de un usuario.

El sistema final deberá:

1. Construir una caracterización inmobiliaria de cada barrio.
2. Incorporar tiempos reales de desplazamiento.
3. Aplicar restricciones obligatorias, como presupuesto máximo o tiempo máximo de viaje.
4. Identificar alternativas eficientes mediante optimización multiobjetivo.
5. Ordenar las alternativas según su similitud con el perfil del usuario.
6. Generar recomendaciones comprensibles y justificadas.

La unidad territorial definitiva del sistema es el **barrio oficial de Madrid**.

Los distritos se conservan como nivel territorial superior, pero no se mezclan con los barrios como si fueran unidades equivalentes.

---

## 2. Planteamiento metodológico

El proyecto se organiza en tres grandes capas.

### 2.1. Capa inmobiliaria

Caracteriza la oferta inmobiliaria de cada barrio a partir de anuncios de viviendas en venta.

Entre las variables calculadas se encuentran:

* Precio total medio y mediano.
* Precio por metro cuadrado medio y mediano.
* Cuartiles e intervalo intercuartílico del precio.
* Superficie media y mediana.
* Número medio y mediano de habitaciones.
* Número medio y mediano de baños cuando existe información suficiente.
* Porcentaje de viviendas con ascensor.
* Porcentaje de viviendas exteriores.
* Número de anuncios válidos.
* Cobertura y fiabilidad de la estimación de precio.

### 2.2. Capa de accesibilidad

Incorporará los tiempos de desplazamiento desde cada barrio hasta uno o varios destinos relevantes para el usuario.

El transporte público real es un requisito obligatorio del proyecto.

También podrán incorporarse, como variables complementarias:

* Tiempo en coche.
* Tiempo andando.
* Tiempo en bicicleta.
* Distancia del recorrido.

No se utilizará el tiempo estimado en coche como sustituto del transporte público.

### 2.3. Capa de recomendación

La propuesta metodológica del sistema final combina:

1. **Filtros obligatorios**, para eliminar barrios incompatibles con las restricciones del usuario.
2. **Frontera de Pareto**, para identificar barrios no dominados en el equilibrio entre precio y tiempo de desplazamiento.
3. **KNN**, para ordenar las alternativas según su similitud con el perfil completo del usuario.
4. **Explicaciones**, para justificar por qué se recomienda cada barrio.

El flujo previsto es:

```text
Preferencias del usuario
        ↓
Aplicación de restricciones
        ↓
Selección de alternativas no dominadas
        ↓
Ordenación personalizada mediante similitud
        ↓
Recomendaciones explicadas
```

---

## 3. Fuentes de datos

### 3.1. Anuncios inmobiliarios

El dataset inmobiliario inicial procede de Kaggle:

* **Dataset:** Idealista MADRID.
* **Autor en Kaggle:** `fjcob1`.
* **Enlace:** https://www.kaggle.com/datasets/fjcob1/idealista-madrid

El archivo original utilizado en el proyecto se conserva como:

```text
data/raw/historical/idealista_listings_unknown_date.csv
```

El dataset contiene una fotografía fija de anuncios de viviendas en venta publicados en Idealista en Madrid.

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

El dataset se utiliza como fuente histórica de anuncios de oferta. Sus precios no deben interpretarse como precios finales de compraventa.

La fecha exacta de recopilación no ha podido determinarse, por lo que este aspecto se conserva expresamente como una limitación del estudio.

### 3.2. División territorial oficial

La delimitación de barrios procede del conjunto oficial:

* **Dataset:** Barrios municipales de Madrid.
* **Publicador:** Ayuntamiento de Madrid.
* **Licencia:** CC BY 4.0.
* **Número de distritos:** 21.
* **Número de barrios:** 131.

Los archivos originales se almacenan en:

```text
data/raw/official/
```

A partir del archivo geográfico oficial se genera la tabla territorial maestra:

```text
data/processed/zones_master.csv
```

Esta tabla contiene para cada barrio:

* Identificador territorial estable.
* Código y nombre del barrio.
* Código y nombre del distrito.
* Latitud representativa.
* Longitud representativa.
* Superficie aproximada en kilómetros cuadrados.

---

## 4. Pipeline de preparación de datos

El pipeline inmobiliario actual sigue esta secuencia:

```text
Dataset original de Kaggle
        ↓
Auditoría inicial
        ↓
Construcción de la tabla territorial oficial
        ↓
Asignación de anuncios a barrios
        ↓
Limpieza de precios y atributos
        ↓
Detección de operaciones especiales
        ↓
Detección y tratamiento de posibles duplicados
        ↓
Selección de anuncios aptos
        ↓
Agregación inmobiliaria por barrio
```

---

## 5. Notebooks

Los notebooks deben ejecutarse siguiendo su numeración.

### `01_auditoria_datos.ipynb`

Realiza la auditoría inicial del dataset inmobiliario.

Incluye:

* Lectura del archivo original.
* Revisión de dimensiones y columnas.
* Análisis de tipos de datos.
* Evaluación de valores ausentes.
* Comprobación de enlaces duplicados.
* Inspección de las zonas y localizaciones.
* Identificación inicial de problemas de calidad.

### `02_validacion_zonas.ipynb`

Construye y valida la estructura territorial del proyecto.

Incluye:

* Lectura de los barrios oficiales de Madrid.
* Generación de un identificador territorial estable.
* Obtención de coordenadas representativas.
* Correspondencia entre las subzonas de Idealista y los barrios oficiales.
* Validación de los casos dudosos.
* Comprobación de que cada anuncio queda asociado a una unidad territorial válida.

El resultado principal es:

```text
data/processed/zones_master.csv
```

### `03_limpieza_anuncios.ipynb`

Realiza la limpieza completa de los anuncios inmobiliarios.

Incluye:

* Conversión de precios a formato numérico.
* Conversión de superficies.
* Cálculo del precio por metro cuadrado.
* Limpieza del número de habitaciones.
* Recuperación del número de baños cuando es posible.
* Normalización de ascensor.
* Identificación de viviendas exteriores o interiores.
* Limpieza y clasificación de plantas.
* Identificación del tipo de inmueble.
* Detección de operaciones inmobiliarias especiales.
* Detección de posibles usos no residenciales.
* Identificación de posibles anuncios duplicados.
* Decisión sobre qué anuncios deben utilizarse en el modelo.

Entre las operaciones especiales detectadas se encuentran:

* Viviendas ocupadas o vendidas sin posesión.
* Nuda propiedad o usufructo.
* Participaciones o proindivisos.
* Subastas.
* Viviendas vendidas con inquilino.
* Inmuebles no residenciales.

Los principales resultados son:

```text
data/processed/listings_clean.csv
data/processed/listings_market_eligible.csv
```

### `04_agregacion_barrios.ipynb`

Construye la caracterización inmobiliaria de los 131 barrios oficiales.

Incluye:

* Agregación de anuncios por barrio.
* Estadísticas de precio total.
* Estadísticas de precio por metro cuadrado.
* Estadísticas de superficie.
* Estadísticas de habitaciones y baños.
* Cobertura de ascensor y exterior.
* Cálculo de intervalos de confianza.
* Evaluación del tamaño de la muestra.
* Construcción de una puntuación de fiabilidad del precio.
* Identificación de barrios sin datos o con muestras insuficientes.

Los principales resultados son:

```text
data/processed/neighborhood_coverage_audit.csv
data/processed/neighborhood_price_uncertainty.csv
data/processed/neighborhood_real_estate_summary.csv
```

### `05_tiempos_transporte.ipynb`

Fase pendiente.

Su objetivo será calcular los tiempos de desplazamiento desde cada barrio hasta los destinos definidos.

Deberá incorporar transporte público real y podrá incluir también:

* Coche.
* Caminando.
* Bicicleta.

Los resultados deberán conservar la trazabilidad de:

* Origen.
* Destino.
* Modo de transporte.
* Fecha y hora de cálculo.
* Fuente utilizada.
* Duración.
* Distancia.
* Estado de la consulta.

### `06_dataset_recomendador.ipynb`

Fase pendiente.

Integrará:

* Resumen inmobiliario por barrio.
* Fiabilidad del precio.
* Tiempos de desplazamiento.
* Variables adicionales que se incorporen posteriormente.

El resultado será el dataset maestro utilizado por el recomendador.

### `07_recomendador.ipynb`

Fase pendiente.

Implementará y evaluará:

* Restricciones del usuario.
* Frontera de Pareto.
* KNN.
* Sistema híbrido.
* Explicaciones de las recomendaciones.
* Comparación entre métodos.
* Evaluación mediante perfiles de usuario.

---

## 6. Estructura del proyecto

```text
TFG_Recomendador_Viviendas/
│
├── data/
│   ├── raw/
│   │   ├── historical/
│   │   │   └── idealista_listings_unknown_date.csv
│   │   │
│   │   └── official/
│   │       ├── madrid_barrios_shp.zip
│   │       └── madrid_barrios_metadata.json
│   │
│   ├── validation/
│   │   └── special_transaction_validation_reviewed.csv
│   │
│   ├── interim/
│   │   └── resultados temporales del procesamiento
│   │
│   └── processed/
│       ├── zones_master.csv
│       ├── zones_master.geojson
│       ├── listings_clean.csv
│       ├── listings_market_eligible.csv
│       ├── neighborhood_coverage_audit.csv
│       ├── neighborhood_price_uncertainty.csv
│       └── neighborhood_real_estate_summary.csv
│
├── notebooks/
│   ├── 01_auditoria_datos.ipynb
│   ├── 02_validacion_zonas.ipynb
│   ├── 03_limpieza_anuncios.ipynb
│   ├── 04_agregacion_barrios.ipynb
│   ├── 05_tiempos_transporte.ipynb
│   ├── 06_dataset_recomendador.ipynb
│   └── 07_recomendador.ipynb
│
├── src/
│   └── data_collection/
│       └── download_madrid_neighborhoods.py
│
├── docs/
├── .gitignore
├── README.md
└── requirements.txt
```

Los archivos de `data/interim/` son resultados intermedios generados durante la limpieza. No todos necesitan almacenarse permanentemente en Git, ya que pueden reconstruirse ejecutando los notebooks.

---

## 7. Estado actual

El pipeline inmobiliario se encuentra implementado hasta la agregación por barrios.

Resultados actuales:

| Indicador                                   | Resultado |
| ------------------------------------------- | --------: |
| Anuncios originales                         |    11.826 |
| Anuncios aptos para el análisis del mercado |    11.109 |
| Distritos oficiales                         |        21 |
| Barrios oficiales                           |       131 |
| Barrios con datos inmobiliarios             |       129 |
| Barrios sin datos inmobiliarios             |         2 |
| Barrios con fiabilidad alta                 |        19 |
| Barrios con fiabilidad media                |        44 |
| Barrios con fiabilidad baja                 |        63 |
| Barrios con muestra insuficiente            |         3 |

Los dos barrios sin anuncios válidos son:

* Atocha.
* Valdebernardo.

Estos barrios no recibirán un precio igual a cero. Se conservarán como barrios sin información inmobiliaria suficiente o se complementarán posteriormente mediante otra fuente.

---

## 8. Evaluación de la fiabilidad inmobiliaria

El número de anuncios disponible es muy desigual entre barrios.

Por este motivo, el sistema no utiliza únicamente una estimación de precio, sino también variables de incertidumbre y fiabilidad.

La fiabilidad se calcula considerando factores como:

* Número de anuncios.
* Precisión del intervalo de confianza de la mediana.
* Dispersión interna del precio por metro cuadrado.
* Existencia o ausencia de datos.

Entre las variables generadas se encuentran:

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

Estas variables permitirán:

* Advertir cuando una recomendación se base en pocos anuncios.
* Penalizar barrios con estimaciones poco fiables.
* Excluir barrios con muestras insuficientes en determinados experimentos.
* Comparar recomendaciones con y sin ajuste por fiabilidad.

---

## 9. Variables inmobiliarias principales

Las variables con mayor interés para el futuro recomendador son:

### Variables económicas

* Precio total mediano.
* Precio por metro cuadrado mediano.
* Intervalo de confianza del precio.
* Puntuación de fiabilidad.

### Variables de tamaño

* Superficie media y mediana.
* Número medio y mediano de habitaciones.

### Características de las viviendas

* Proporción de viviendas con ascensor.
* Proporción de viviendas exteriores.

### Variables de cobertura

* Número de anuncios.
* Porcentaje de anuncios válidos.
* Cobertura conocida de cada atributo.

El número de baños se conserva como variable informativa, pero actualmente presenta una cobertura limitada y no deberá tener un peso principal en el recomendador sin una validación adicional.

---

## 10. Instalación

Se recomienda utilizar un entorno virtual de Python.

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux o macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

El entorno virtual no debe incluirse en GitHub ni en los archivos enviados al tutor.

---

## 11. Dependencias principales

Las dependencias actuales incluyen:

```text
pandas
numpy
matplotlib
geopandas
jupyter
ipykernel
```

Las dependencias específicas de rutas, transporte y recomendación se incorporarán cuando se implementen las fases correspondientes.

---

## 12. Ejecución

Abrir el proyecto desde su carpeta raíz y ejecutar:

```bash
jupyter notebook
```

También puede utilizarse Jupyter desde Visual Studio Code.

Los notebooks deben ejecutarse en orden:

```text
01_auditoria_datos.ipynb
02_validacion_zonas.ipynb
03_limpieza_anuncios.ipynb
04_agregacion_barrios.ipynb
05_tiempos_transporte.ipynb
06_dataset_recomendador.ipynb
07_recomendador.ipynb
```

En el estado actual, los notebooks implementados y validados son los correspondientes a las fases 01–04.

---

## 13. Reproducibilidad

Para favorecer la reproducibilidad:

* Los datos originales se conservan sin modificaciones.
* Cada fase genera archivos de salida diferenciados.
* Las decisiones manuales relevantes se guardan en archivos de validación.
* Las unidades territoriales se identifican mediante `zone_key`.
* Los anuncios conservan su referencia a la fuente original.
* Los resultados agregados pueden reconstruirse ejecutando los notebooks.
* Las limitaciones del dataset se registran explícitamente.
* Las futuras consultas de transporte deberán guardar fecha, hora, modo y fuente.

No deben modificarse manualmente los archivos almacenados en `data/raw/`.

---

## 14. Limitaciones actuales

### Fecha del dataset inmobiliario

No se conoce con precisión la fecha de recopilación de los anuncios originales.

Por ello, los precios representan una muestra histórica de oferta y no deben interpretarse como una descripción exacta del mercado actual.

### Precios de oferta

Los datos representan precios anunciados, no precios finales de transacción.

### Cobertura desigual

El número de anuncios varía considerablemente entre barrios.

Las recomendaciones deberán tener en cuenta la puntuación de fiabilidad y no tratar todas las estimaciones como igualmente precisas.

### Falta de datos en algunos barrios

Atocha y Valdebernardo no disponen actualmente de anuncios válidos.

### Cobertura de atributos

Algunas características, especialmente el número de baños, tienen una cobertura limitada.

### Transporte pendiente

La capa de accesibilidad todavía no está integrada.

El sistema no estará completo hasta incorporar tiempos reales de transporte público.

### Ausencia de comportamiento histórico de usuarios

No se dispone de valoraciones ni interacciones históricas de usuarios.

Por tanto, KNN se utilizará como método de similitud basado en contenido, no como filtrado colaborativo.

---

## 15. Evaluación prevista

El recomendador se evaluará mediante varios perfiles representativos.

Ejemplos:

### Estudiante

* Presupuesto reducido.
* Prioridad alta al transporte público.
* Aceptación de menor superficie.
* Destino habitual en una universidad o zona céntrica.

### Profesional

* Presupuesto medio o alto.
* Prioridad alta al tiempo de desplazamiento.
* Preferencia por ascensor y mayor superficie.
* Destino habitual en una zona de oficinas.

### Familia

* Necesidad de varias habitaciones.
* Preferencia por mayor superficie.
* Equilibrio entre coste y accesibilidad.
* Posible incorporación de servicios cercanos.

Para cada perfil se analizarán:

* Barrios recomendados.
* Cumplimiento de restricciones.
* Precio y tiempo de desplazamiento.
* Fiabilidad de los datos.
* Presencia en la frontera de Pareto.
* Cambios en el ranking al modificar las preferencias.

---

## 16. Comparación de métodos

Se prevé comparar al menos los siguientes enfoques:

1. Ranking ponderado sin Pareto.
2. KNN sin filtrado Pareto.
3. Pareto sin KNN.
4. Sistema híbrido de filtros, Pareto y KNN.

Entre las métricas y criterios de comparación podrán incluirse:

* Porcentaje de recomendaciones dentro del presupuesto.
* Porcentaje de recomendaciones dentro del tiempo máximo.
* Número de alternativas dominadas recomendadas.
* Distancia respecto al perfil solicitado.
* Diversidad de los resultados.
* Estabilidad ante cambios pequeños en las preferencias.
* Calidad y fiabilidad de los datos de los barrios recomendados.

---

## 17. Próximas fases

### Fase 1. Limpieza final del repositorio

* Eliminar archivos vacíos y resultados antiguos.
* Evitar incluir el entorno virtual.
* Mantener un único notebook por fase.
* Actualizar la documentación.
* Crear y mantener `requirements.txt`.

### Fase 2. Transporte

* Seleccionar una fuente válida de transporte público.
* Definir los destinos de prueba.
* Definir la fecha y hora de las consultas.
* Calcular tiempos desde los 131 barrios.
* Conservar la trazabilidad de todas las rutas.
* Analizar errores y barrios sin ruta.

### Fase 3. Dataset maestro

* Integrar la información inmobiliaria con la accesibilidad.
* Definir las variables definitivas.
* Normalizar las escalas.
* Tratar barrios sin datos.
* Incorporar la fiabilidad de precios.

### Fase 4. Recomendador

* Implementar filtros.
* Implementar Pareto.
* Implementar KNN.
* Generar explicaciones.
* Evaluar diferentes perfiles.
* Comparar métodos.

### Fase 5. Aplicación

Como ampliación del proyecto, podrá desarrollarse una interfaz que permita:

* Introducir preferencias.
* Seleccionar un destino.
* Consultar los barrios recomendados.
* Visualizar el equilibrio entre precio y desplazamiento.
* Mostrar las razones de cada recomendación.
* Representar los resultados sobre un mapa.

---

## 18. Contribución esperada

La contribución principal del proyecto es transformar datos inmobiliarios y territoriales heterogéneos en un sistema de apoyo a la decisión residencial.

El trabajo incluye:

* Auditoría de datos reales.
* Limpieza e ingeniería de características.
* Normalización de unidades territoriales.
* Correspondencia entre zonas inmobiliarias y barrios oficiales.
* Tratamiento de operaciones inmobiliarias especiales.
* Evaluación de incertidumbre y fiabilidad.
* Integración futura con datos de movilidad.
* Optimización multiobjetivo.
* Personalización de recomendaciones.
* Generación de resultados interpretables.

El resultado esperado no es una única respuesta universal, sino un conjunto de alternativas justificadas y adaptadas a las prioridades de cada usuario.

---

## 19. Estado del desarrollo

**Implementado:**

* Auditoría del dataset inmobiliario.
* Construcción de la tabla de 131 barrios oficiales.
* Correspondencia territorial de los anuncios.
* Limpieza de precios, superficies y atributos.
* Detección de operaciones especiales.
* Detección y resolución de posibles duplicados.
* Selección de anuncios aptos.
* Agregación inmobiliaria por barrio.
* Evaluación de cobertura, incertidumbre y fiabilidad.

**Pendiente:**

* Validación externa de precios.
* Incorporación de transporte público real.
* Construcción del dataset maestro.
* Implementación del recomendador.
* Evaluación comparativa.
* Desarrollo de una posible interfaz.

---

## 20. Uso académico y licencias

Este repositorio se desarrolla como parte de un Trabajo de Fin de Grado.

Los datos externos mantienen sus correspondientes condiciones de uso y licencias.

Antes de redistribuir los datos brutos procedentes de Kaggle o de otras plataformas, deben consultarse sus términos específicos. Los datos oficiales del Ayuntamiento de Madrid utilizados para la delimitación territorial se publican bajo licencia CC BY 4.0.

El código y la documentación desarrollados específicamente para el TFG deberán incorporar la licencia que se determine para el repositorio.
