# TFG Recomendador de Viviendas

El proyecto ya no tiene que quedarse en comparar modelos de prediccion de precio. La base que encaja mejor con el objetivo del TFG es:

1. Construir un dataset agregado por `zone_key` con variables inmobiliarias.
2. Integrar tiempos de desplazamiento hacia destinos relevantes.
3. Formular la recomendacion como un problema multiobjetivo `precio vs tiempo`.
4. Evaluar resultados para distintos perfiles de usuario.

## Archivos clave

- [data/datos_zone_ml.csv](./data/datos_zone_ml.csv): dataset agregado por zonas.
- [data/accessibility_template.csv](./data/accessibility_template.csv): plantilla para cargar tiempos de viaje por zona y destino.
- [src/recommendation_pipeline.py](./src/recommendation_pipeline.py): funciones reutilizables para el notebook.

## Flujo recomendado en el notebook

```python
import sys
from pathlib import Path

sys.path.append(str(Path.cwd().resolve().parents[0]))

from src.recommendation_pipeline import (
    DEFAULT_PROFILES,
    attach_accessibility_features,
    compute_pareto_front,
    load_accessibility_data,
    load_zone_data,
    rank_zones_for_profile,
    hybrid_knn_recommendation,
)

zones = load_zone_data("../data/datos_zone_ml.csv")
acc = load_accessibility_data("../data/accessibility_template.csv")

df_model = attach_accessibility_features(zones, acc)
pareto_sol = compute_pareto_front(df_model, time_col="tt_sol")

perfil = DEFAULT_PROFILES["estudiante_centro"]
top_zonas = rank_zones_for_profile(df_model, perfil, time_col="tt_sol", top_n=5)

knn_top = hybrid_knn_recommendation(
    df_model,
    user_preferences={
        "precio_objetivo": 350000,
        "metros_objetivo": 60,
        "habitaciones_objetivo": 2,
        "banos_objetivo": 1,
        "tiempo_objetivo_min": 30,
    },
    time_col="tt_sol",
    n_neighbors=5,
)
```

## Como defender el enfoque

- La regresion de precios puede quedarse como analisis auxiliar, no como nucleo del recomendador.
- La frontera de Pareto permite identificar zonas no dominadas en el trade-off entre precio y accesibilidad.
- Los perfiles de usuario sirven para validar que el sistema cambia sus recomendaciones segun preferencias reales.
- El KNN tiene sentido si se usa como capa de similitud y despues se reordena con una funcion de utilidad que incluya el tiempo de viaje.

## Siguiente paso importante

Rellenar `data/accessibility_template.csv` con tiempos reales desde cada `zone_key` a destinos como `sol`, `cuatro_caminos` y `las_tablas`. En cuanto esos tiempos existan, el pipeline ya puede ejecutarse sin cambios estructurales.

## Script para construir tiempos de desplazamiento

Se ha anadido `src/build_accessibility_dataset.py` para rellenar automaticamente la plantilla de accesibilidad usando OpenRouteService.

### 1) Definir API key

```powershell
$env:ORS_API_KEY="TU_API_KEY"
```

### 2) Ejecutar el script

```powershell
python src/build_accessibility_dataset.py \
    --template data/accessibility_template.csv \
    --output data/accessibility_template_filled.csv
```

Opciones utiles:

- `--overwrite`: recalcula tambien las filas que ya tengan tiempo.
- `--sleep-seconds 0.5`: reduce riesgo de rate limiting.

Nota: ORS no ofrece perfil nativo de transporte publico. En esta version, `modo=transporte_publico` se estima con perfil `driving-car` y se etiqueta como `_proxy` en `fuente` para mantener trazabilidad metodologica.

## Material para memoria

- Texto de metodologia y resultados listo para adaptar: `docs/metodologia_resultados_tfg.md`
- Bloque de analisis adicional en notebook: `notebooks/dataset_exploration.ipynb`
