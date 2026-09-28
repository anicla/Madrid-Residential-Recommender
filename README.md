# Recomendador de zonas residenciales en Madrid

Este proyecto corresponde a mi Trabajo de Fin de Grado en Ingeniería Informática en la Universidad Carlos III de Madrid (UC3M).

El objetivo es desarrollar un sistema capaz de recomendar zonas residenciales de Madrid teniendo en cuenta dos factores principales: el precio de la vivienda y el tiempo de desplazamiento diario. La idea surge de un problema habitual a la hora de buscar vivienda: las zonas más económicas no siempre son las mejor comunicadas y, por tanto, es necesario encontrar un equilibrio entre ambos criterios.

El sistema analiza los 131 barrios oficiales de Madrid y permite adaptar las recomendaciones a las preferencias y restricciones de cada usuario.

## Funcionamiento

El proceso de recomendación se divide en varias etapas:

1. Recopilación, limpieza e integración de datos procedentes de distintas fuentes.
2. Cálculo de los tiempos de desplazamiento mediante OpenTripPlanner.
3. Obtención de la frontera de Pareto utilizando el precio y el tiempo como objetivos.
4. Aplicación de las preferencias del usuario mediante diferentes perfiles y pesos configurables.
5. Aplicación de restricciones de presupuesto y tiempo máximo de desplazamiento.
6. Uso de K-Nearest Neighbors (KNN) para explorar zonas similares a las recomendadas.
7. Presentación de los resultados mediante una aplicación interactiva desarrollada con Streamlit.

## Frontera de Pareto

El precio y el tiempo de desplazamiento son los dos criterios principales utilizados para comparar las zonas.

La frontera de Pareto permite identificar aquellas alternativas para las que no existe otra zona que sea simultáneamente mejor en ambos criterios. De esta forma se eliminan las alternativas dominadas antes de aplicar las preferencias particulares del usuario.

Sobre las zonas resultantes se calcula posteriormente una puntuación en función del peso que el usuario quiera dar al precio y al tiempo.

## Exploración mediante KNN

Además de la recomendación principal, se utiliza K-Nearest Neighbors para encontrar alternativas similares teniendo en cuenta características adicionales de las viviendas.

Entre las variables utilizadas se encuentran:

- Superficie.
- Número de habitaciones.
- Número de baños.
- Ascensor.
- Vivienda exterior.

KNN se utiliza como mecanismo de exploración complementario y no como sustituto del proceso de recomendación basado en Pareto y preferencias.

## Cálculo de los desplazamientos

Los tiempos de desplazamiento se obtienen mediante OpenTripPlanner ejecutado en local, utilizando información de transporte público y datos cartográficos.

Se consideran cuatro modos de transporte:

- Transporte público.
- A pie.
- Bicicleta.
- Coche.

Los tiempos calculados se combinan posteriormente con la información de precios para construir la base utilizada por el recomendador.

## Aplicación interactiva

El sistema cuenta con una aplicación desarrollada con Streamlit que permite configurar la recomendación de forma interactiva.

El usuario puede seleccionar:

- Destino.
- Medio de transporte.
- Perfil de preferencias.
- Peso asignado al precio y al tiempo.
- Presupuesto máximo.
- Tiempo máximo de desplazamiento.

A partir de estos parámetros, la aplicación muestra las zonas recomendadas y permite consultar alternativas similares mediante KNN.

## Evaluación

El sistema se evaluó utilizando 36 escenarios, correspondientes a 12 combinaciones de destino y modo de transporte y tres perfiles de preferencias.

Además de comprobar el correcto funcionamiento del proceso completo de recomendación, se analizó la estabilidad de los resultados ante cambios en las preferencias y su robustez frente a pequeñas perturbaciones en los datos.

Entre los resultados obtenidos destaca una robustez del Top-5 de aproximadamente el 93,68 % ante perturbaciones del 5 %.

## Tecnologías utilizadas

- Python
- Pandas
- NumPy
- Scikit-learn
- Streamlit
- OpenTripPlanner
- Jupyter Notebook
- GTFS
- OpenStreetMap

## Estructura del repositorio

```text
.
├── data/                 # Datos utilizados y generados durante el proyecto
├── docs/                 # Documentación
├── figures_memoria/      # Figuras y resultados gráficos
├── notebooks/            # Desarrollo, análisis y evaluación
├── routing/otp/          # Procesamiento de rutas con OpenTripPlanner
├── src/data_collection/  # Obtención y preparación de los datos
├── app.py                 # Aplicación desarrollada con Streamlit
├── requirements.txt      # Dependencias del proyecto
└── requirements_app.txt  # Dependencias de la aplicación
```

## Ejecución

Para ejecutar la aplicación es necesario clonar primero el repositorio:

```bash
git clone https://github.com/anicla/Madrid-Residential-Recommender.git
cd Madrid-Residential-Recommender
```

A continuación, instalar las dependencias necesarias:

```bash
pip install -r requirements_app.txt
```

Por último, iniciar la aplicación de Streamlit:

```bash
streamlit run app.py
```

## Fuentes de datos

Para el desarrollo del proyecto se han utilizado datos procedentes de distintas fuentes:

- Ayuntamiento de Madrid.
- Consorcio Regional de Transportes de Madrid (CRTM).
- OpenStreetMap.
- Datos de Idealista disponibles a través de Kaggle.

Los datos se utilizan de acuerdo con las condiciones de reutilización de cada fuente. En particular, los datos de Idealista obtenidos a través de Kaggle se han utilizado únicamente con finalidad académica y de investigación.

## Autora

**Ana Claver Miranda**

Trabajo de Fin de Grado en Ingeniería Informática  
Universidad Carlos III de Madrid (UC3M)
