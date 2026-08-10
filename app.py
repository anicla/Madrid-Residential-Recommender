"""
Demo interactiva del TFG:
Sistema de recomendación de vivienda en Madrid basado en
Pareto + preferencias del usuario + KNN.

Ejecución:
    streamlit run app.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Recomendador de vivienda · Madrid",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Recomendador de zonas de vivienda en Madrid")

st.markdown(
    """
Esta aplicación utiliza el sistema desarrollado en el TFG para buscar zonas que
ofrezcan un buen equilibrio entre **precio de vivienda** y **tiempo de desplazamiento**.

La recomendación se construye en tres pasos:

1. se identifican las alternativas **Pareto eficientes**;
2. se selecciona la que mejor encaja con tus preferencias;
3. se buscan barrios similares mediante **KNN**, manteniendo únicamente alternativas Pareto.
"""
)


# ============================================================
# 2. FUNCIONES AUXILIARES
# ============================================================

def find_project_root():
    """
    Busca la raíz del proyecto localizando la carpeta data.

    Esto permite ejecutar app.py tanto desde la raíz del proyecto
    como desde otra subcarpeta.
    """
    current = Path.cwd().resolve()

    for candidate in [current, *current.parents]:
        if (candidate / "data").exists():
            return candidate

    # Si el archivo se encuentra dentro del proyecto, probamos también
    # a partir de la propia ubicación de app.py.
    file_dir = Path(__file__).resolve().parent

    for candidate in [file_dir, *file_dir.parents]:
        if (candidate / "data").exists():
            return candidate

    raise FileNotFoundError(
        "No se ha encontrado la carpeta 'data' del proyecto."
    )


def first_existing_column(df, candidates, required=False, label=None):
    """
    Devuelve la primera columna existente de una lista de candidatos.
    """
    for column in candidates:
        if column in df.columns:
            return column

    if required:
        raise KeyError(
            f"No se ha encontrado la columna necesaria para "
            f"{label or candidates}. Candidatas: {candidates}"
        )

    return None


def minmax(series):
    """
    Normalización min-max.

    Se utiliza para que precio y tiempo puedan combinarse
    en una misma función de preferencias.
    """
    series = pd.to_numeric(series, errors="coerce")

    min_value = series.min()
    max_value = series.max()

    if pd.isna(min_value) or pd.isna(max_value):
        return pd.Series(np.nan, index=series.index)

    if np.isclose(min_value, max_value):
        return pd.Series(0.0, index=series.index)

    return (series - min_value) / (max_value - min_value)


def pareto_mask_minimize(df, price_col, time_col):
    """
    Calcula la frontera de Pareto para dos objetivos que se minimizan:
    precio y tiempo.

    Una alternativa queda dominada si existe otra que no es peor
    en ninguno de los dos objetivos y mejora al menos uno.
    """
    values = df[[price_col, time_col]].to_numpy(dtype=float)
    efficient = np.ones(len(values), dtype=bool)

    for i, point in enumerate(values):
        dominates_point = (
            (values[:, 0] <= point[0])
            & (values[:, 1] <= point[1])
            & (
                (values[:, 0] < point[0])
                | (values[:, 1] < point[1])
            )
        )

        dominates_point[i] = False
        efficient[i] = not dominates_point.any()

    return efficient


def prepare_destination_matrix(group, feature_cols):
    """
    Prepara las variables usadas por KNN.

    - convierte las columnas a numérico;
    - imputa únicamente variables auxiliares con la mediana;
    - estandariza las escalas con StandardScaler.
    """
    X = group[feature_cols].copy()

    for column in feature_cols:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce",
        )

        median = X[column].median()

        if pd.isna(median):
            median = 0.0

        X[column] = X[column].fillna(median)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled


def select_anchor(
    destination_df,
    price_col,
    time_col,
    price_weight,
    time_weight,
):
    """
    Selecciona la alternativa Pareto que mejor encaja
    con los pesos indicados por el usuario.
    """
    group = destination_df.copy()

    group["price_norm_app"] = minmax(group[price_col])
    group["time_norm_app"] = minmax(group[time_col])

    pareto_group = group[
        group["is_pareto_app"]
    ].copy()

    pareto_group["profile_score_app"] = (
        price_weight * pareto_group["price_norm_app"]
        + time_weight * pareto_group["time_norm_app"]
    )

    anchor = pareto_group.sort_values(
        [
            "profile_score_app",
            price_col,
            time_col,
        ]
    ).iloc[0]

    return anchor


def find_pareto_neighbors(
    destination_df,
    anchor_zone_id,
    zone_id_col,
    feature_cols,
    k,
):
    """
    Busca los k barrios Pareto más similares a la recomendación principal.

    El propio barrio recomendado se excluye de la lista de vecinos.
    """
    group = destination_df.reset_index(drop=True).copy()

    X_scaled = prepare_destination_matrix(
        group,
        feature_cols,
    )

    anchor_positions = group.index[
        group[zone_id_col] == anchor_zone_id
    ].tolist()

    if not anchor_positions:
        return pd.DataFrame()

    anchor_position = anchor_positions[0]

    candidate_positions = group.index[
        group["is_pareto_app"]
    ].tolist()

    if anchor_position in candidate_positions:
        candidate_positions.remove(anchor_position)

    if not candidate_positions:
        return pd.DataFrame()

    n_neighbors = min(
        int(k),
        len(candidate_positions),
    )

    model = NearestNeighbors(
        n_neighbors=n_neighbors,
        metric="euclidean",
    )

    candidate_matrix = X_scaled[
        candidate_positions
    ]

    model.fit(candidate_matrix)

    distances, local_indices = model.kneighbors(
        X_scaled[[anchor_position]],
        return_distance=True,
    )

    rows = []

    for rank, (distance, local_index) in enumerate(
        zip(distances[0], local_indices[0]),
        start=1,
    ):
        position = candidate_positions[
            int(local_index)
        ]

        row = group.iloc[position].copy()
        row["knn_rank_app"] = rank
        row["knn_distance_app"] = float(distance)

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def format_number(value, decimals=1):
    """
    Formato seguro para valores numéricos mostrados en la interfaz.
    """
    if pd.isna(value):
        return "—"

    return f"{value:,.{decimals}f}"


# ============================================================
# 3. CARGA DE DATOS
# ============================================================

@st.cache_data
def load_data():
    """
    Carga y valida el dataset principal utilizado por el recomendador.
    """
    project_root = find_project_root()
    results_dir = project_root / "data" / "results"
    input_path = results_dir / "pareto_by_destination.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo esperado: {input_path}"
        )

    df = pd.read_csv(input_path)

    return df, project_root


try:
    data, PROJECT_ROOT = load_data()
except Exception as exc:
    st.error(
        "No se ha podido cargar el dataset del recomendador."
    )
    st.exception(exc)
    st.stop()


# ============================================================
# 4. IDENTIFICACIÓN DE COLUMNAS
# ============================================================

try:
    ZONE_ID_COL = first_existing_column(
        data,
        ["zone_key", "neighborhood_id", "zone_id"],
        required=True,
        label="identificador de barrio",
    )

    ZONE_NAME_COL = first_existing_column(
        data,
        ["zone_name", "neighborhood_name", "barrio", "name"],
    )

    DEST_COL = first_existing_column(
        data,
        ["destination_name", "destination"],
        required=True,
        label="destino",
    )

    PRICE_COL = first_existing_column(
        data,
        [
            "price_m2_for_recommender",
            "price_m2",
            "registered_price_m2_total_2025",
        ],
        required=True,
        label="precio",
    )

    TIME_COL = first_existing_column(
        data,
        [
            "commute_daily_minutes",
            "commute_minutes",
            "travel_time_minutes",
        ],
        required=True,
        label="tiempo de desplazamiento",
    )

except Exception as exc:
    st.error(
        "El archivo existe, pero no contiene las columnas esperadas."
    )
    st.exception(exc)
    st.stop()


# ============================================================
# 5. PREPARACIÓN DEL DATASET
# ============================================================

work = data.copy()

work[PRICE_COL] = pd.to_numeric(
    work[PRICE_COL],
    errors="coerce",
)

work[TIME_COL] = pd.to_numeric(
    work[TIME_COL],
    errors="coerce",
)

# Los dos objetivos principales no se imputan.
work = work.dropna(
    subset=[
        ZONE_ID_COL,
        DEST_COL,
        PRICE_COL,
        TIME_COL,
    ]
).copy()

work = work[
    (work[PRICE_COL] > 0)
    & (work[TIME_COL] >= 0)
].copy()

# Calculamos Pareto dentro de cada destino.
work["is_pareto_app"] = False

for destination, indices in work.groupby(
    DEST_COL
).groups.items():
    group = work.loc[indices]

    work.loc[
        indices,
        "is_pareto_app",
    ] = pareto_mask_minimize(
        group,
        PRICE_COL,
        TIME_COL,
    )


# ============================================================
# 6. VARIABLES AUXILIARES PARA KNN
# ============================================================

OPTIONAL_FEATURE_GROUPS = {
    "superficie": [
        "size_mean",
        "size_median",
        "sale_size",
        "metros_mean",
        "metros_median",
    ],
    "habitaciones": [
        "rooms_mean",
        "sale_rooms",
        "habitaciones_mean",
    ],
    "banos": [
        "baths_mean",
        "sale_baths",
        "banos_mean",
    ],
    "ascensor": [
        "elevator_ratio",
        "ascensor_ratio",
    ],
    "exterior": [
        "exterior_ratio",
    ],
}

optional_features = []

for _, candidates in OPTIONAL_FEATURE_GROUPS.items():
    column = first_existing_column(
        work,
        candidates,
    )

    if column is not None and column not in optional_features:
        optional_features.append(column)

KNN_FEATURES = [
    PRICE_COL,
    TIME_COL,
] + optional_features


# ============================================================
# 7. PANEL DE PREFERENCIAS
# ============================================================

st.sidebar.header("Tus preferencias")

destinations = sorted(
    work[DEST_COL]
    .dropna()
    .astype(str)
    .unique()
)

selected_destination = st.sidebar.selectbox(
    "Destino habitual",
    destinations,
)

profile_option = st.sidebar.selectbox(
    "Perfil",
    [
        "Equilibrado",
        "Estudiante",
        "Profesional",
        "Personalizado",
    ],
)

PROFILE_WEIGHTS = {
    "Estudiante": (0.80, 0.20),
    "Equilibrado": (0.50, 0.50),
    "Profesional": (0.25, 0.75),
}

if profile_option == "Personalizado":
    price_weight_pct = st.sidebar.slider(
        "Importancia del precio (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5,
    )

    price_weight = (
        price_weight_pct / 100
    )

    time_weight = (
        1 - price_weight
    )

    st.sidebar.caption(
        f"Tiempo de desplazamiento: "
        f"{100 - price_weight_pct} %"
    )

else:
    (
        price_weight,
        time_weight,
    ) = PROFILE_WEIGHTS[
        profile_option
    ]

    st.sidebar.write(
        f"**Precio:** {price_weight:.0%}"
    )
    st.sidebar.write(
        f"**Tiempo:** {time_weight:.0%}"
    )


# Número de alternativas similares.
k_neighbors = st.sidebar.slider(
    "Alternativas similares",
    min_value=1,
    max_value=10,
    value=5,
    step=1,
)


# ============================================================
# 8. FILTROS OPCIONALES
# ============================================================

destination_df = work[
    work[DEST_COL].astype(str)
    == str(selected_destination)
].copy()

st.sidebar.divider()
st.sidebar.subheader(
    "Restricciones opcionales"
)

use_price_limit = st.sidebar.checkbox(
    "Limitar precio por m²"
)

max_price = None

if use_price_limit:
    price_min = float(
        destination_df[PRICE_COL].min()
    )
    price_max = float(
        destination_df[PRICE_COL].max()
    )

    max_price = st.sidebar.slider(
        "Precio máximo (€/m²)",
        min_value=int(np.floor(price_min)),
        max_value=int(np.ceil(price_max)),
        value=int(np.ceil(price_max)),
        step=max(
            1,
            int(
                (price_max - price_min)
                / 50
            ),
        ),
    )

use_time_limit = st.sidebar.checkbox(
    "Limitar tiempo diario"
)

max_time = None

if use_time_limit:
    time_min = float(
        destination_df[TIME_COL].min()
    )
    time_max = float(
        destination_df[TIME_COL].max()
    )

    max_time = st.sidebar.slider(
        "Tiempo máximo diario (min)",
        min_value=int(np.floor(time_min)),
        max_value=int(np.ceil(time_max)),
        value=int(np.ceil(time_max)),
        step=1,
    )


# Aplicamos las restricciones antes de recalcular Pareto.
filtered_df = destination_df.copy()

if max_price is not None:
    filtered_df = filtered_df[
        filtered_df[PRICE_COL]
        <= max_price
    ].copy()

if max_time is not None:
    filtered_df = filtered_df[
        filtered_df[TIME_COL]
        <= max_time
    ].copy()

if filtered_df.empty:
    st.warning(
        "No existen zonas que cumplan simultáneamente las restricciones seleccionadas."
    )
    st.stop()


# La frontera se vuelve a calcular sobre las alternativas compatibles.
filtered_df["is_pareto_app"] = pareto_mask_minimize(
    filtered_df,
    PRICE_COL,
    TIME_COL,
)


# ============================================================
# 9. RECOMENDACIÓN PRINCIPAL
# ============================================================

anchor = select_anchor(
    destination_df=filtered_df,
    price_col=PRICE_COL,
    time_col=TIME_COL,
    price_weight=price_weight,
    time_weight=time_weight,
)

anchor_zone_id = anchor[
    ZONE_ID_COL
]

anchor_name = (
    anchor[ZONE_NAME_COL]
    if ZONE_NAME_COL is not None
    else anchor_zone_id
)

st.subheader(
    "Recomendación principal"
)

st.success(
    f"**{anchor_name}** es la alternativa Pareto que mejor "
    f"encaja con las preferencias seleccionadas."
)

metric_col1, metric_col2, metric_col3 = st.columns(
    3
)

metric_col1.metric(
    "Precio",
    f"{format_number(anchor[PRICE_COL], 2)} €/m²",
)

metric_col2.metric(
    "Tiempo diario",
    f"{format_number(anchor[TIME_COL], 1)} min",
)

metric_col3.metric(
    "Puntuación",
    format_number(
        anchor["profile_score_app"],
        3,
    ),
)


# ============================================================
# 10. EXPLICACIÓN DE LA RECOMENDACIÓN
# ============================================================

cheapest = filtered_df.sort_values(
    PRICE_COL
).iloc[0]

fastest = filtered_df.sort_values(
    TIME_COL
).iloc[0]

price_vs_cheapest = (
    100
    * (
        anchor[PRICE_COL]
        - cheapest[PRICE_COL]
    )
    / cheapest[PRICE_COL]
)

if np.isclose(
    fastest[TIME_COL],
    0,
):
    time_vs_fastest = np.nan
else:
    time_vs_fastest = (
        100
        * (
            anchor[TIME_COL]
            - fastest[TIME_COL]
        )
        / fastest[TIME_COL]
    )

st.markdown(
    f"""
### ¿Por qué esta zona?

La recomendación no busca únicamente el barrio más barato ni el trayecto más rápido.

- Frente a la alternativa de menor precio, la zona recomendada presenta una diferencia de
  **{price_vs_cheapest:+.1f} %** en €/m².
- Frente a la alternativa con menor tiempo, presenta una diferencia de
  **{time_vs_fastest:+.1f} %** en tiempo diario.
- La zona pertenece a la **frontera de Pareto**, por lo que no existe otra alternativa
  compatible que la mejore simultáneamente en precio y tiempo.
"""
)


# ============================================================
# 11. ALTERNATIVAS SIMILARES PARETO + KNN
# ============================================================

neighbors = find_pareto_neighbors(
    destination_df=filtered_df,
    anchor_zone_id=anchor_zone_id,
    zone_id_col=ZONE_ID_COL,
    feature_cols=KNN_FEATURES,
    k=k_neighbors,
)

st.subheader(
    "Alternativas similares"
)

st.caption(
    "Las siguientes zonas se buscan mediante KNN únicamente "
    "entre alternativas Pareto eficientes."
)

if neighbors.empty:
    st.info(
        "No existen suficientes alternativas Pareto para mostrar vecinos."
    )
else:
    neighbors_display = pd.DataFrame()

    neighbors_display["Posición"] = neighbors[
        "knn_rank_app"
    ].astype(int)

    if ZONE_NAME_COL is not None:
        neighbors_display["Zona"] = neighbors[
            ZONE_NAME_COL
        ].values
    else:
        neighbors_display["Zona"] = neighbors[
            ZONE_ID_COL
        ].values

    neighbors_display["Precio (€/m²)"] = (
        neighbors[PRICE_COL]
        .astype(float)
        .round(2)
        .values
    )

    neighbors_display["Tiempo diario (min)"] = (
        neighbors[TIME_COL]
        .astype(float)
        .round(1)
        .values
    )

    neighbors_display["Distancia KNN"] = (
        neighbors["knn_distance_app"]
        .astype(float)
        .round(3)
        .values
    )

    st.dataframe(
        neighbors_display,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 12. GRÁFICO PRECIO - TIEMPO
# ============================================================

st.subheader(
    "Relación entre precio y desplazamiento"
)

fig, ax = plt.subplots(
    figsize=(9, 6)
)

ax.scatter(
    filtered_df[PRICE_COL],
    filtered_df[TIME_COL],
    alpha=0.40,
    label="Zonas compatibles",
)

pareto_df = filtered_df[
    filtered_df["is_pareto_app"]
].sort_values(
    PRICE_COL
)

ax.scatter(
    pareto_df[PRICE_COL],
    pareto_df[TIME_COL],
    s=65,
    label="Frontera de Pareto",
)

ax.scatter(
    [anchor[PRICE_COL]],
    [anchor[TIME_COL]],
    marker="*",
    s=230,
    label="Recomendación",
)

if not neighbors.empty:
    ax.scatter(
        neighbors[PRICE_COL],
        neighbors[TIME_COL],
        marker="x",
        s=90,
        label="Alternativas KNN",
    )

ax.set_xlabel(
    "Precio de vivienda (€/m²)"
)

ax.set_ylabel(
    "Tiempo diario de desplazamiento (min)"
)

ax.set_title(
    f"Precio vs tiempo · {selected_destination}"
)

ax.grid(
    alpha=0.25
)

ax.legend()

st.pyplot(
    fig,
    use_container_width=True,
)


# ============================================================
# 13. DETALLE DEL PERFIL Y DEL MODELO
# ============================================================

with st.expander(
    "Ver cómo se ha calculado la recomendación"
):
    st.markdown(
        f"""
**Preferencias aplicadas**

- Peso del precio: **{price_weight:.0%}**
- Peso del tiempo: **{time_weight:.0%}**

**Proceso**

1. Se filtran las zonas que cumplen las restricciones.
2. Se calcula la frontera de Pareto.
3. Precio y tiempo se normalizan dentro del destino seleccionado.
4. Se calcula una puntuación ponderada según tus preferencias.
5. La alternativa Pareto con menor puntuación se utiliza como recomendación principal.
6. KNN busca hasta **{k_neighbors}** zonas similares dentro de la propia frontera de Pareto.

**Variables utilizadas por KNN**

`{", ".join(KNN_FEATURES)}`
"""
    )


# ============================================================
# 14. INFORMACIÓN DEL CONJUNTO ANALIZADO
# ============================================================

with st.expander(
    "Información de cobertura"
):
    total_destination = len(
        destination_df
    )

    total_compatible = len(
        filtered_df
    )

    total_pareto = int(
        filtered_df[
            "is_pareto_app"
        ].sum()
    )

    st.write(
        f"Zonas disponibles para el destino: "
        f"**{total_destination}**"
    )

    st.write(
        f"Zonas compatibles con las restricciones: "
        f"**{total_compatible}**"
    )

    st.write(
        f"Zonas Pareto eficientes: "
        f"**{total_pareto}**"
    )


# ============================================================
# 15. NOTA METODOLÓGICA
# ============================================================

st.divider()

st.caption(
    "El sistema recomienda zonas agregadas y no viviendas concretas. "
    "Los tiempos proceden del pipeline de transporte del proyecto y "
    "los precios corresponden a los datos preparados en los notebooks previos."
)
