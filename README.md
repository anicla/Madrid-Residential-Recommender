# Sistema de recomendación multimodal de barrios residenciales en Madrid

Trabajo de Fin de Grado centrado en el desarrollo y evaluación de un sistema de apoyo a la decisión residencial para Madrid. El sistema integra información inmobiliaria, información territorial y accesibilidad multimodal para recomendar **barrios oficiales** en función de las preferencias y restricciones del usuario.

El problema se formula como una decisión multicriterio en la que los dos objetivos principales son minimizar:

- el **precio de referencia de la vivienda**;
- el **tiempo diario de desplazamiento**.

El modo de transporte no se introduce como un tercer objetivo. Se trata como una **preferencia categórica** que determina qué alternativas pueden compararse entre sí.

## 1. Estado del proyecto

El pipeline principal se encuentra implementado hasta la validación final del recomendador y se ha desarrollado además una extensión experimental **Pareto + KNN** y una aplicación interactiva con Streamlit.

El flujo general es:

```text
Datos inmobiliarios + división territorial oficial
                    ↓
Auditoría, validación territorial y limpieza
                    ↓
Agregación y fiabilidad inmobiliaria por barrio
                    ↓
Integración de referencia oficial de precios
                    ↓
OpenTripPlanner: accesibilidad multimodal
                    ↓
Dataset barrio × destino × modo
                    ↓
Pareto precio–tiempo
                    ↓
Personalización por pesos y restricciones
                    ↓
Evaluación experimental y validación final
                    ↓
Extensión Pareto + KNN
                    ↓
Aplicación Streamlit
```

La unidad territorial definitiva es el **barrio oficial de Madrid**. Los distritos se conservan como nivel territorial superior, pero no se mezclan con los barrios como si fueran unidades equivalentes.

## 2. Datos utilizados

### 2.1. Anuncios inmobiliarios

La fuente histórica inicial de anuncios procede de Kaggle:

- **Dataset:** Idealista MADRID.
- **Autor:** `fjcob1`.
- **Archivo conservado:** `data/raw/historical/idealista_listings_unknown_date.csv`.

La fecha exacta de recopilación del dataset no ha podido determinarse. Por tanto, los anuncios se utilizan como una muestra histórica de oferta y no como una fotografía exacta del mercado actual.

Los precios de los anuncios son **precios de oferta**, no precios finales de transacción.

### 2.2. División territorial oficial

La delimitación territorial procede de los datos abiertos del Ayuntamiento de Madrid.

El proyecto trabaja con:

- **21 distritos**;
- **131 barrios oficiales**.

La tabla territorial maestra es:

```text
data/processed/zones_master.csv
```

La clave `zone_key` se utiliza como identificador estable para integrar las distintas fuentes.

### 2.3. Referencia oficial de precios

El notebook 05 incorpora una referencia oficial de precios de vivienda y genera, entre otros, los siguientes archivos:

```text
data/processed/registered_housing_price_2025.csv
data/processed/neighborhood_real_estate_enriched.csv
data/processed/neighborhood_real_estate_integration_audit.csv
```

La integración permite diferenciar entre la información histórica de los anuncios y la referencia territorial oficial utilizada posteriormente por el recomendador.

### 2.4. Movilidad

La accesibilidad se calcula con una instancia local de **OpenTripPlanner (OTP)** construida con:

- GTFS oficiales del Consorcio Regional de Transportes de Madrid;
- OpenStreetMap para la red peatonal, ciclista y viaria;
- coordenadas representativas de los 131 barrios;
- destinos definidos en `data/reference/destinations.csv`.

Se consideran cuatro modos:

| Código | Modo |
|---|---|
| `TRANSIT` | Transporte público |
| `WALK` | A pie |
| `BICYCLE` | Bicicleta |
| `CAR` | Coche |

Para cada combinación se analizan dos desplazamientos diarios:

- llegada al destino por la mañana;
- salida del destino por la tarde.

Con 131 barrios, 3 destinos, 2 escenarios y 4 modos, la ejecución definitiva de transporte contempla:

```text
131 × 3 × 2 × 4 = 3.144 consultas
```

## 3. Unidades de análisis

Es importante distinguir tres niveles.

### Consulta de transporte

Cada solicitud a OTP queda identificada por:

```text
fecha de servicio × barrio × destino × escenario × modo
```

### Alternativa del recomendador

Después de combinar ida y vuelta, cada alternativa representa:

```text
barrio × destino × modo
```

### Grupo de comparación

Pareto, las normalizaciones y los rankings se calculan siempre dentro de:

```text
destino × modo
```

De esta forma no se mezclan tiempos correspondientes a estrategias de movilidad diferentes.

## 4. Tratamiento de rutas no disponibles

Las rutas no disponibles se conservan de forma explícita.

Los estados permiten distinguir entre:

- `complete_route`;
- `partial_route`;
- `no_route`;
- errores técnicos.

Los tiempos ausentes **no se imputan** con medias, máximos ni valores de otros barrios. Una imputación sobre el tiempo de desplazamiento podría alterar artificialmente la frontera de Pareto.

Los casos sin información suficiente se mantienen en los datasets de auditoría, pero no se utilizan cuando es necesario comparar simultáneamente precio y tiempo.

## 5. Metodología del recomendador

### 5.1. Restricciones

Antes de generar una recomendación pueden aplicarse límites como:

- precio máximo por metro cuadrado;
- presupuesto territorial orientativo para una superficie de referencia;
- tiempo diario máximo de desplazamiento;
- fiabilidad mínima de la estimación inmobiliaria.

### 5.2. Frontera de Pareto

Los dos objetivos centrales son:

```text
minimizar precio
minimizar tiempo diario de desplazamiento
```

Una alternativa es Pareto eficiente cuando no existe otra que sea igual o mejor en ambos objetivos y estrictamente mejor en al menos uno.

Cuando el usuario aplica restricciones, la frontera se vuelve a calcular dentro del conjunto compatible.

### 5.3. Personalización

El ranking utiliza una suma ponderada:

```text
score =
    peso_precio × precio_normalizado
    + peso_tiempo × tiempo_normalizado
```

Cuanto menor es la puntuación, mejor encaja la alternativa.

Los perfiles reproducibles utilizados en la evaluación son:

| Perfil | Precio | Tiempo |
|---|---:|---:|
| Prioridad al precio | 0,75 | 0,25 |
| Perfil equilibrado | 0,50 | 0,50 |
| Prioridad al tiempo | 0,25 | 0,75 |

Las normalizaciones de precio y tiempo se fijan por grupo **destino × modo** en el notebook 08. Aplicar o retirar filtros no modifica artificialmente esa escala de referencia.

La fiabilidad inmobiliaria puede utilizarse como filtro y desempate secundario, pero no sustituye a los dos objetivos principales.

## 6. Extensión Pareto + KNN

Los notebooks 12 y 13 estudian una capa adicional de similitud.

KNN no se utiliza como predictor ni como estimador de satisfacción. Su función es recuperar barrios parecidos a una recomendación personalizada.

La comparación distingue:

- `KNN_global`: búsqueda entre todas las alternativas comparables;
- `Pareto_KNN`: búsqueda restringida a alternativas Pareto eficientes.

Las matrices KNN se construyen por **destino × modo**. Precio y tiempo forman siempre parte del espacio de características. Las variables residenciales auxiliares solo se incorporan cuando tienen cobertura y variación suficientes.

Las variables se estandarizan con `StandardScaler`. Los valores ausentes de variables auxiliares pueden imputarse con la mediana del grupo exclusivamente para calcular similitud. **Precio y tiempo no se imputan.**

La evaluación de la extensión analiza, entre otros aspectos:

- coste de similitud al exigir eficiencia Pareto;
- sensibilidad a `k`;
- diferencias entre perfiles;
- diferencias entre modos;
- ablación del espacio de características;
- estabilidad descriptiva mediante bootstrap.

## 7. Notebooks

La secuencia lógica del proyecto es:

```text
01_auditoria_datos.ipynb
02_validacion_zonas.ipynb
03_limpieza_anuncios.ipynb
04_agregacion_barrios.ipynb
05_integracion_fuentes_inmobiliarias.ipynb
06_tiempos_transporte.ipynb
07_dataset_recomendador.ipynb
08_pareto_recomendador.ipynb
09_recomendacion_personalizada.ipynb
10_evaluacion_experimental_recomendador.ipynb
11_validacion_final_recomendador.ipynb
12_extension_hibrida_pareto_knn.ipynb
13_evaluacion_experimental_hibrida.ipynb
```

Antes de la entrega conviene mantener **un único archivo definitivo por notebook** y utilizar nombres canónicos sin sufijos como `(1)`, `_FINAL` o `_MATRICULA`.

### 01 · Auditoría de datos

Analiza el dataset inmobiliario original, su estructura, tipos, valores ausentes, duplicados y principales problemas de calidad.

### 02 · Validación de zonas

Construye y valida la correspondencia entre los anuncios y los 131 barrios oficiales de Madrid.

### 03 · Limpieza de anuncios

Limpia precios, superficies y atributos, identifica operaciones inmobiliarias especiales, usos no residenciales y posibles duplicados.

### 04 · Agregación por barrios

Construye las variables inmobiliarias agregadas y las medidas de cobertura, incertidumbre y fiabilidad.

### 05 · Integración de fuentes inmobiliarias

Integra la información histórica de anuncios con la referencia oficial de precios manteniendo trazabilidad y auditoría.

### 06 · Tiempos de transporte

Calcula la matriz multimodal con OpenTripPlanner para `TRANSIT`, `WALK`, `BICYCLE` y `CAR`.

Genera:

```text
data/processed/transport_route_requests_audit.csv
data/processed/transport_route_itineraries.csv
data/processed/transport_routes_by_neighborhood.csv
```

### 07 · Dataset del recomendador

Integra información inmobiliaria y movilidad.

La relación entre ambas capas es de uno a varios: un barrio aparece una vez en la capa inmobiliaria y varias veces en movilidad, una por cada destino y modo.

Entre las salidas principales se encuentran:

```text
data/final/neighborhood_recommender_dataset.csv
data/final/neighborhood_recommender_model_ready.csv
```

### 08 · Pareto

Calcula la eficiencia multiobjetivo por **destino × modo**.

Entre sus salidas:

```text
data/results/pareto_by_destination_mode.csv
data/results/pareto_front_by_destination_mode.csv
data/results/pareto_summary_by_destination_mode.csv
```

### 09 · Recomendación personalizada

Implementa restricciones, pesos, ranking personalizado, explicaciones y validaciones del motor.

Entre sus salidas:

```text
data/results/recommendation_profiles.csv
data/results/profile_recommendation_comparison_by_destination_mode.csv
data/results/recommendation_engine_multimodal_validation.csv
```

### 10 · Evaluación experimental

Compara el método principal con métodos de referencia y estudia eficiencia, estabilidad, robustez, personalización y diversidad.

La unidad experimental es:

```text
destino × modo × perfil
```

### 11 · Validación final

Comprueba la coherencia extremo a extremo de los notebooks 08–10 y genera una síntesis final reproducible.

Entre sus salidas:

```text
data/results/final_multimodal_validation_report.csv
data/results/final_multimodal_summary.csv
```

### 12 · Extensión híbrida Pareto + KNN

Construye y evalúa vecinos similares dentro de cada grupo destino–modo, comparando KNN global con Pareto + KNN.

Entre sus salidas:

```text
data/results/knn12_multimodal_validation_report.csv
data/results/knn12_multimodal_neighbors_k5.csv
data/results/knn12_multimodal_strategy_comparison.csv
```

### 13 · Evaluación experimental de la extensión

Cierra la evaluación de la capa KNN mediante sensibilidad a `k`, perfiles, características, modos y bootstrap.

Entre sus salidas:

```text
data/results/evaluation13_multimodal_validation_report.csv
data/results/evaluation13_multimodal_summary.csv
```

## 8. Aplicación interactiva

La aplicación se encuentra en:

```text
app.py
```

Consume:

```text
data/results/pareto_by_destination_mode.csv
```

La interfaz permite:

- seleccionar destino;
- seleccionar modo de transporte;
- utilizar perfiles predefinidos o pesos personalizados;
- aplicar restricciones de precio, presupuesto orientativo, tiempo y fiabilidad;
- obtener una recomendación Pareto personalizada;
- consultar alternativas similares mediante Pareto + KNN;
- visualizar el equilibrio precio–tiempo;
- consultar la auditoría de filtros y las variables utilizadas.

La aplicación no recalcula rutas. Si los CSV del pipeline ya existen, **OpenTripPlanner y Docker no son necesarios durante el uso de Streamlit**.

### Ejecución de la aplicación

Desde la raíz del proyecto:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements_app.txt
streamlit run app.py
```

En Linux o macOS:

```bash
source venv/bin/activate
pip install -r requirements_app.txt
streamlit run app.py
```

## 9. OpenTripPlanner y reproducibilidad del transporte

Para volver a generar las rutas es necesario disponer de la instancia local de OTP.

El endpoint utilizado por el notebook 06 es:

```text
http://localhost:8080/otp/gtfs/v1
```

Si el contenedor ya existe, puede iniciarse con:

```powershell
docker start otp-madrid
```

El notebook 06 incorpora un modo de prueba y un sistema de reanudación. La ejecución definitiva debe realizarse únicamente después de superar las validaciones del test multimodal.

Los resultados se identifican mediante una clave canónica que incluye la fecha de servicio para evitar mezclar ejecuciones diferentes.

## 10. Estructura orientativa del repositorio

```text
TFG_Recomendador_Viviendas/
│
├── app.py
├── README.md
├── requirements.txt
├── requirements_app.txt
│
├── data/
│   ├── raw/
│   │   ├── historical/
│   │   └── official/
│   ├── reference/
│   │   └── destinations.csv
│   ├── validation/
│   ├── interim/
│   ├── processed/
│   ├── final/
│   └── results/
│
├── notebooks/
│   ├── 01_auditoria_datos.ipynb
│   ├── 02_validacion_zonas.ipynb
│   ├── 03_limpieza_anuncios.ipynb
│   ├── 04_agregacion_barrios.ipynb
│   ├── 05_integracion_fuentes_inmobiliarias.ipynb
│   ├── 06_tiempos_transporte.ipynb
│   ├── 07_dataset_recomendador.ipynb
│   ├── 08_pareto_recomendador.ipynb
│   ├── 09_recomendacion_personalizada.ipynb
│   ├── 10_evaluacion_experimental_recomendador.ipynb
│   ├── 11_validacion_final_recomendador.ipynb
│   ├── 12_extension_hibrida_pareto_knn.ipynb
│   └── 13_evaluacion_experimental_hibrida.ipynb
│
├── src/
└── docs/
```

Los archivos intermedios que puedan reconstruirse no tienen por qué mantenerse todos en Git. Los datos originales de `data/raw/` no deben modificarse manualmente.

## 11. Dependencias de la aplicación

`requirements_app.txt` contiene:

```text
streamlit
pandas
numpy
matplotlib
scikit-learn
```

Las dependencias del pipeline completo pueden mantenerse por separado en `requirements.txt`.

## 12. Reproducibilidad y trazabilidad

El proyecto aplica varias medidas para facilitar la reproducibilidad:

- conservación de los datos originales;
- archivos diferenciados por etapa;
- uso de `zone_key` como identificador territorial;
- claves únicas para las consultas de transporte;
- auditorías de rutas, uniones y filtros;
- validaciones automáticas entre notebooks;
- separación entre errores técnicos y rutas no disponibles;
- ausencia de imputación en los objetivos principales;
- normalización por grupo destino–modo;
- desempates reproducibles;
- resultados experimentales exportados a CSV.

## 13. Limitaciones

Los resultados deben interpretarse dentro del alcance del TFG.

- La fecha exacta de recopilación de los anuncios históricos no es conocida.
- Los anuncios representan precios de oferta, no precios finales de compraventa.
- El número de observaciones inmobiliarias es desigual entre barrios.
- La referencia territorial no equivale a una valoración de una vivienda concreta.
- Cada barrio se representa mediante una coordenada de referencia, por lo que no se modela su variabilidad espacial interna.
- Los tiempos dependen de la fecha, los horarios y los datos de routing disponibles.
- El coche no incorpora tráfico en tiempo real.
- Los recorridos a pie y en bicicleta dependen de la representación de la red en OpenStreetMap.
- Las rutas ausentes no se imputan.
- No existe un experimento con usuarios reales ni una prueba A/B.
- Los perfiles son configuraciones reproducibles de preferencias, no segmentos poblacionales estimados.
- KNN es una capa de similitud basada en contenido y no filtrado colaborativo.
- Las distancias KNN se calculan dentro de cada grupo destino–modo y no constituyen una escala física universal.
- La frontera de Pareto garantiza eficiencia únicamente respecto a precio y tiempo.

## 14. Aplicación académica

El repositorio se desarrolla como parte de un Trabajo de Fin de Grado.

Los datos externos mantienen sus condiciones de uso y licencias correspondientes. Antes de redistribuir datos brutos procedentes de Kaggle o de otras plataformas deben revisarse sus términos específicos.

Los datos oficiales del Ayuntamiento de Madrid utilizados para la delimitación territorial se publican bajo licencia CC BY 4.0.

La licencia del código y de la documentación desarrollados específicamente para el TFG deberá definirse explícitamente antes de publicar el repositorio de forma definitiva.
