"""
Aplicación interactiva del TFG:
Sistema de recomendación multimodal de barrios residenciales en Madrid.

La aplicación consume los resultados ya generados por el pipeline:
    data/results/pareto_by_destination_mode.csv

Ejecución:
    streamlit run app.py

Nota:
    OpenTripPlanner no necesita estar ejecutándose para usar la aplicación
    si los CSV del pipeline ya han sido generados.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from pandas.api.types import is_bool_dtype
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Recomendador residencial multimodal · Madrid",
    page_icon="🏠",
    layout="wide",
)

PRICE_COLUMN = "price_m2_for_recommender"
TIME_COLUMN = "commute_daily_minutes"

GROUP_KEY = [
    "destination_id",
    "transport_mode",
]

ALTERNATIVE_KEY = [
    "zone_key",
    "destination_id",
    "transport_mode",
]

EXPECTED_MODES = {
    "TRANSIT": "Transporte público",
    "WALK": "A pie",
    "BICYCLE": "Bicicleta",
    "CAR": "Coche",
}

MODE_ICONS = {
    "TRANSIT": "🚇",
    "WALK": "🚶",
    "BICYCLE": "🚲",
    "CAR": "🚗",
}

PROFILE_WEIGHTS = {
    "Prioridad al precio": (0.75, 0.25),
    "Perfil equilibrado": (0.50, 0.50),
    "Prioridad al tiempo": (0.25, 0.75),
}

REQUIRED_COLUMNS = [
    "zone_key",
    "neighborhood_name",
    "district_name",
    "destination_id",
    "destination_name",
    "transport_mode",
    "transport_mode_label",
    PRICE_COLUMN,
    TIME_COLUMN,
    "is_pareto",
    "price_normalized",
    "time_normalized",
]

OPTIONAL_KNN_FEATURE_GROUPS = {
    "surface": [
        "area_m2_median",
        "area_m2_mean",
        "size_median",
        "size_mean",
        "surface_median",
        "surface_mean",
        "sale_size",
        "metros_median",
        "metros_mean",
    ],
    "rooms": [
        "rooms_median",
        "rooms_mean",
        "sale_rooms",
        "habitaciones_median",
        "habitaciones_mean",
    ],
    "bathrooms": [
        "bathrooms_median",
        "bathrooms_mean",
        "baths_median",
        "baths_mean",
        "sale_baths",
        "banos_median",
        "banos_mean",
    ],
    "elevator": [
        "elevator_ratio",
        "ascensor_ratio",
    ],
    "exterior": [
        "exterior_ratio",
    ],
}

OPTIONAL_DISPLAY_COLUMNS = {
    "Fiabilidad del precio": [
        "price_reliability_score",
    ],
    "Nivel de fiabilidad": [
        "price_reliability_level",
    ],
    "Fuente del precio": [
        "price_m2_for_recommender_source",
    ],
    "Distancia diaria (m)": [
        "commute_daily_distance_meters",
        "commute_daily_distance",
        "daily_distance_meters",
    ],
    "Tiempo andando diario (min)": [
        "commute_daily_walk_minutes",
    ],
    "Tiempo de espera diario (min)": [
        "commute_daily_waiting_minutes",
    ],
    "Transbordos diarios": [
        "commute_daily_transfers",
    ],
}

TOLERANCE = 1e-9


# ============================================================
# 2. FUNCIONES AUXILIARES
# ============================================================

def find_project_root() -> Path:
    """
    Busca la raíz del proyecto usando como contrato el archivo
    pareto_by_destination_mode.csv.
    """
    required = (
        Path("data")
        / "results"
        / "pareto_by_destination_mode.csv"
    )

    candidates = []

    current = Path.cwd().resolve()
    candidates.extend([current, *current.parents])

    try:
        file_dir = Path(__file__).resolve().parent
        candidates.extend([file_dir, *file_dir.parents])
    except NameError:
        pass

    seen = set()

    for candidate in candidates:
        candidate = candidate.resolve()

        if candidate in seen:
            continue

        seen.add(candidate)

        if (candidate / required).exists():
            return candidate

    raise FileNotFoundError(
        "No se ha localizado la raíz del proyecto. "
        "Debe existir data/results/pareto_by_destination_mode.csv. "
        "Ejecuta primero los notebooks 08–11."
    )


def parse_boolean_series(
    series: pd.Series,
    column_name: str,
) -> pd.Series:
    """Convierte de forma estricta una columna a booleano."""
    if is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    normalized = (
        series.astype("string")
        .str.strip()
        .str.lower()
    )

    true_values = {
        "true",
        "1",
        "yes",
        "y",
        "si",
        "sí",
    }

    false_values = {
        "false",
        "0",
        "no",
        "n",
    }

    valid_values = true_values | false_values

    invalid = (
        normalized.notna()
        & ~normalized.isin(valid_values)
    )

    if invalid.any():
        examples = sorted(
            normalized.loc[invalid]
            .dropna()
            .unique()
            .tolist()
        )[:10]

        raise ValueError(
            f"Valores no reconocidos en {column_name}: "
            f"{examples}"
        )

    return (
        normalized.isin(true_values)
        .fillna(False)
        .astype(bool)
    )


def first_existing_column(
    frame: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    """Devuelve la primera columna disponible de una lista."""
    for column in candidates:
        if column in frame.columns:
            return column

    return None


def pareto_mask_minimize(
    frame: pd.DataFrame,
    price_col: str = PRICE_COLUMN,
    time_col: str = TIME_COLUMN,
) -> np.ndarray:
    """
    Calcula la frontera de Pareto para dos objetivos a minimizar.

    Una alternativa queda dominada si existe otra que no es peor
    en ningún objetivo y mejora estrictamente al menos uno.
    """
    values = frame[
        [
            price_col,
            time_col,
        ]
    ].to_numpy(dtype=float)

    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError(
            "La matriz de objetivos debe tener exactamente dos columnas."
        )

    if not np.isfinite(values).all():
        raise ValueError(
            "No se puede calcular Pareto con valores no finitos."
        )

    efficient = np.ones(
        len(values),
        dtype=bool,
    )

    for index, point in enumerate(values):
        dominates_point = (
            (values[:, 0] <= point[0] + TOLERANCE)
            & (values[:, 1] <= point[1] + TOLERANCE)
            & (
                (values[:, 0] < point[0] - TOLERANCE)
                | (values[:, 1] < point[1] - TOLERANCE)
            )
        )

        dominates_point[index] = False
        efficient[index] = not dominates_point.any()

    return efficient


def select_optional_knn_features(
    frame: pd.DataFrame,
    minimum_coverage: float = 0.70,
) -> tuple[list[str], pd.DataFrame]:
    """
    Selecciona variables residenciales auxiliares para KNN.

    Una variable auxiliar se incorpora únicamente si:
    - existe;
    - al menos el 70 % de sus valores son numéricos no ausentes;
    - presenta variación.

    Precio y tiempo siempre forman parte del espacio KNN.
    """
    selected = []
    audit_rows = []

    for feature_group, candidates in (
        OPTIONAL_KNN_FEATURE_GROUPS.items()
    ):
        column = first_existing_column(
            frame,
            candidates,
        )

        if column is None:
            audit_rows.append(
                {
                    "Grupo": feature_group,
                    "Columna": "—",
                    "Cobertura": 0.0,
                    "Valores distintos": 0,
                    "Incluida": False,
                    "Motivo": "No disponible",
                }
            )
            continue

        numeric = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        coverage = float(
            numeric.notna().mean()
        )

        unique_values = int(
            numeric.dropna().nunique()
        )

        included = (
            coverage >= minimum_coverage
            and unique_values >= 2
        )

        if included:
            frame[column] = numeric
            selected.append(column)

        audit_rows.append(
            {
                "Grupo": feature_group,
                "Columna": column,
                "Cobertura": coverage,
                "Valores distintos": unique_values,
                "Incluida": included,
                "Motivo": (
                    "Incluida"
                    if included
                    else "Cobertura < 70 % o sin variación"
                ),
            }
        )

    return (
        selected,
        pd.DataFrame(audit_rows),
    )


def build_knn_matrix(
    group: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    """
    Estandariza las variables dentro del grupo destino × modo.

    Los objetivos precio y tiempo no se imputan.
    Las variables auxiliares pueden imputarse con la mediana
    exclusivamente para calcular similitud.
    """
    matrix = group[
        feature_columns
    ].copy()

    for column in feature_columns:
        matrix[column] = pd.to_numeric(
            matrix[column],
            errors="coerce",
        )

        if column in {
            PRICE_COLUMN,
            TIME_COLUMN,
        }:
            if matrix[column].isna().any():
                raise ValueError(
                    "Los objetivos principales no pueden imputarse "
                    f"para KNN: {column}."
                )
        else:
            median = matrix[column].median()

            if pd.isna(median):
                raise ValueError(
                    "No se puede imputar la variable auxiliar "
                    f"{column}: su mediana es NaN."
                )

            matrix[column] = (
                matrix[column]
                .fillna(median)
            )

    scaler = StandardScaler()

    return scaler.fit_transform(
        matrix
    )


def find_pareto_neighbors(
    compatible: pd.DataFrame,
    anchor_zone_key: str,
    feature_columns: list[str],
    k: int,
) -> pd.DataFrame:
    """
    Busca vecinos similares únicamente entre alternativas Pareto
    del conjunto compatible destino × modo.

    La recomendación principal nunca aparece como vecina de sí misma.
    """
    if compatible.empty:
        return pd.DataFrame()

    group = (
        compatible.copy()
        .reset_index(drop=True)
    )

    matrix = build_knn_matrix(
        group,
        feature_columns,
    )

    anchor_positions = group.index[
        group["zone_key"].astype(str).eq(
            str(anchor_zone_key)
        )
    ].tolist()

    if len(anchor_positions) != 1:
        raise ValueError(
            "La recomendación principal no se identifica "
            "de forma única dentro del grupo."
        )

    anchor_position = int(
        anchor_positions[0]
    )

    candidate_positions = [
        int(position)
        for position in group.index[
            group["is_pareto_app"]
        ].tolist()
        if int(position) != anchor_position
    ]

    if not candidate_positions:
        return pd.DataFrame()

    effective_k = min(
        int(k),
        len(candidate_positions),
    )

    model = NearestNeighbors(
        n_neighbors=effective_k,
        metric="euclidean",
        algorithm="auto",
    )

    model.fit(
        matrix[candidate_positions]
    )

    distances, local_indices = (
        model.kneighbors(
            matrix[[anchor_position]],
            return_distance=True,
        )
    )

    rows = []
    dimension = max(
        len(feature_columns),
        1,
    )

    for rank, (
        distance,
        local_index,
    ) in enumerate(
        zip(
            distances[0],
            local_indices[0],
        ),
        start=1,
    ):
        position = candidate_positions[
            int(local_index)
        ]

        row = (
            group.iloc[position]
            .copy()
        )

        row["knn_rank_app"] = rank
        row["knn_distance_app"] = float(
            distance
        )
        row[
            "knn_distance_normalized_app"
        ] = (
            float(distance)
            / np.sqrt(dimension)
        )

        rows.append(row)

    return pd.DataFrame(rows)


def select_recommendation(
    compatible: pd.DataFrame,
    price_weight: float,
    time_weight: float,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Selecciona la recomendación principal.

    La frontera de Pareto se recalcula tras aplicar restricciones,
    pero la puntuación utiliza price_normalized y time_normalized
    ya fijadas por el notebook 08 dentro del grupo destino × modo.

    En caso de empate en la puntuación de preferencia, se prioriza
    la alternativa con mayor fiabilidad del precio. Después se
    utilizan el precio, el tiempo y zone_key como criterios de
    desempate adicionales.
    """
    scored = compatible.copy()

    scored["is_pareto_app"] = (
        pareto_mask_minimize(scored)
    )

    scored["price_score_contribution_app"] = (
        float(price_weight)
        * scored["price_normalized"]
    )

    scored["time_score_contribution_app"] = (
        float(time_weight)
        * scored["time_normalized"]
    )

    scored["preference_score_app"] = (
        scored[
            "price_score_contribution_app"
        ]
        + scored[
            "time_score_contribution_app"
        ]
    )

    candidates = (
        scored.loc[
            scored["is_pareto_app"]
        ]
        .copy()
    )

    if candidates.empty:
        raise ValueError(
            "No existen alternativas Pareto en el conjunto compatible."
        )

    sort_columns = [
        "preference_score_app",
    ]

    ascending = [
        True,
    ]

    if (
        "price_reliability_score"
        in candidates.columns
    ):
        candidates[
            "price_reliability_score"
        ] = pd.to_numeric(
            candidates[
                "price_reliability_score"
            ],
            errors="coerce",
        )

        sort_columns.append(
            "price_reliability_score"
        )
        ascending.append(False)

    sort_columns.extend(
        [
            PRICE_COLUMN,
            TIME_COLUMN,
            "zone_key",
        ]
    )

    ascending.extend(
        [
            True,
            True,
            True,
        ]
    )

    candidates = (
        candidates.sort_values(
            sort_columns,
            ascending=ascending,
            na_position="last",
        )
        .reset_index(drop=True)
    )

    anchor = candidates.iloc[0]

    return (
        anchor,
        scored,
    )


def format_number(
    value,
    decimals: int = 1,
) -> str:
    """Formatea valores numéricos de forma segura."""
    if pd.isna(value):
        return "—"

    return f"{float(value):,.{decimals}f}"


def safe_percentage_difference(
    value: float,
    reference: float,
) -> float:
    """Calcula la diferencia porcentual respecto a una referencia."""
    if (
        not np.isfinite(reference)
        or np.isclose(reference, 0.0)
    ):
        return np.nan

    return (
        100.0
        * (float(value) - float(reference))
        / float(reference)
    )


def profile_priority_text(
    price_weight: float,
    time_weight: float,
) -> str:
    """Describe de forma breve la prioridad de los pesos."""
    if np.isclose(
        price_weight,
        time_weight,
    ):
        return (
            "equilibra por igual precio y tiempo"
        )

    if price_weight > time_weight:
        return (
            "da mayor importancia al precio"
        )

    return (
        "da mayor importancia al tiempo de desplazamiento"
    )


# ============================================================
# 3. CARGA Y VALIDACIÓN DEL DATASET
# ============================================================

@st.cache_data
def load_data() -> tuple[pd.DataFrame, Path]:
    """
    Carga el resultado del notebook 08 y valida su contrato básico.
    """
    project_root = find_project_root()

    input_path = (
        project_root
        / "data"
        / "results"
        / "pareto_by_destination_mode.csv"
    )

    data = pd.read_csv(
        input_path
    )

    missing_columns = sorted(
        set(REQUIRED_COLUMNS)
        - set(data.columns)
    )

    if missing_columns:
        raise KeyError(
            "Faltan columnas necesarias en "
            "pareto_by_destination_mode.csv: "
            f"{missing_columns}"
        )

    for column in [
        "zone_key",
        "neighborhood_name",
        "district_name",
        "destination_id",
        "destination_name",
        "transport_mode",
        "transport_mode_label",
    ]:
        data[column] = (
            data[column]
            .astype("string")
            .str.strip()
        )

    data["transport_mode"] = (
        data["transport_mode"]
        .str.upper()
    )

    for column in [
        PRICE_COLUMN,
        TIME_COLUMN,
        "price_normalized",
        "time_normalized",
    ]:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data["is_pareto"] = (
        parse_boolean_series(
            data["is_pareto"],
            "is_pareto",
        )
    )

    missing_key_values = (
        data[
            ALTERNATIVE_KEY
        ]
        .isna()
        .any(axis=1)
    )

    if missing_key_values.any():
        raise ValueError(
            "Existen alternativas con claves incompletas."
        )

    duplicate_alternatives = (
        data[
            ALTERNATIVE_KEY
        ]
        .duplicated()
    )

    if duplicate_alternatives.any():
        examples = (
            data.loc[
                duplicate_alternatives,
                ALTERNATIVE_KEY,
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "Hay combinaciones barrio–destino–modo duplicadas. "
            f"Ejemplos: {examples}"
        )

    invalid_objectives = (
        data[
            [
                PRICE_COLUMN,
                TIME_COLUMN,
            ]
        ]
        .isna()
        .any(axis=1)
        | (
            data[
                [
                    PRICE_COLUMN,
                    TIME_COLUMN,
                ]
            ]
            <= 0
        ).any(axis=1)
    )

    if invalid_objectives.any():
        raise ValueError(
            "Existen precios o tiempos no válidos en el dataset Pareto."
        )

    normalized = data[
        [
            "price_normalized",
            "time_normalized",
        ]
    ]

    invalid_normalized = (
        normalized.isna().any(axis=1)
        | (normalized < -TOLERANCE).any(axis=1)
        | (normalized > 1 + TOLERANCE).any(axis=1)
    )

    if invalid_normalized.any():
        raise ValueError(
            "Las variables normalizadas deben estar dentro de [0, 1]."
        )

    modes_present = set(
        data["transport_mode"]
        .dropna()
        .astype(str)
        .unique()
    )

    if modes_present != set(EXPECTED_MODES):
        raise ValueError(
            "Los modos disponibles no coinciden con los cuatro esperados. "
            f"Presentes: {sorted(modes_present)}"
        )

    for mode, expected_label in (
        EXPECTED_MODES.items()
    ):
        labels = set(
            data.loc[
                data[
                    "transport_mode"
                ].eq(mode),
                "transport_mode_label",
            ]
            .dropna()
            .astype(str)
            .unique()
        )

        if labels != {
            expected_label
        }:
            raise ValueError(
                f"Etiqueta inconsistente para {mode}: "
                f"{sorted(labels)}"
            )

    return (
        data,
        project_root,
    )


try:
    data, PROJECT_ROOT = load_data()
except Exception as exc:
    st.error(
        "No se ha podido cargar o validar el dataset del recomendador."
    )
    st.exception(exc)
    st.stop()


# ============================================================
# 4. PREPARACIÓN DE VARIABLES AUXILIARES
# ============================================================

work = data.copy()

optional_knn_features, feature_audit = (
    select_optional_knn_features(
        work,
        minimum_coverage=0.70,
    )
)

KNN_FEATURES = [
    PRICE_COLUMN,
    TIME_COLUMN,
    *optional_knn_features,
]

if (
    "price_reliability_score"
    in work.columns
):
    work[
        "price_reliability_score"
    ] = pd.to_numeric(
        work[
            "price_reliability_score"
        ],
        errors="coerce",
    )


# ============================================================
# 5. CABECERA
# ============================================================

st.title(
    "🏠 Recomendador multimodal de barrios de Madrid"
)

st.markdown(
    """
El sistema recomienda **barrios oficiales de Madrid** combinando dos criterios
que pueden entrar en conflicto: **precio de referencia de la vivienda** y
**tiempo diario de desplazamiento**.

El modo de transporte se selecciona como una preferencia categórica.
Cada recomendación se calcula únicamente dentro de una combinación
**destino × modo**, por lo que no se mezclan escalas de movilidad diferentes.
"""
)


# ============================================================
# 6. PANEL DE PREFERENCIAS
# ============================================================

st.sidebar.header(
    "Preferencias"
)

destination_catalog = (
    work[
        [
            "destination_id",
            "destination_name",
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "destination_name",
            "destination_id",
        ]
    )
    .reset_index(drop=True)
)

destination_labels = {
    str(row["destination_id"]): (
        f"{row['destination_name']} "
        f"({row['destination_id']})"
    )
    for _, row in (
        destination_catalog.iterrows()
    )
}

selected_destination_id = (
    st.sidebar.selectbox(
        "Destino habitual",
        options=list(
            destination_labels
        ),
        format_func=lambda value: (
            destination_labels[value]
        ),
    )
)

selected_destination_name = (
    destination_catalog.loc[
        destination_catalog[
            "destination_id"
        ].astype(str).eq(
            str(selected_destination_id)
        ),
        "destination_name",
    ]
    .iloc[0]
)

mode_order = [
    "TRANSIT",
    "WALK",
    "BICYCLE",
    "CAR",
]

selected_mode = (
    st.sidebar.selectbox(
        "Modo de transporte",
        options=mode_order,
        format_func=lambda mode: (
            f"{MODE_ICONS[mode]} "
            f"{EXPECTED_MODES[mode]}"
        ),
    )
)

selected_mode_label = (
    EXPECTED_MODES[
        selected_mode
    ]
)

profile_option = (
    st.sidebar.selectbox(
        "Perfil de preferencias",
        options=[
            "Perfil equilibrado",
            "Prioridad al precio",
            "Prioridad al tiempo",
            "Personalizado",
        ],
    )
)

if profile_option == "Personalizado":
    price_weight_pct = (
        st.sidebar.slider(
            "Importancia del precio (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
        )
    )

    price_weight = (
        price_weight_pct
        / 100.0
    )

    time_weight = (
        1.0
        - price_weight
    )

    st.sidebar.caption(
        "Importancia del tiempo: "
        f"{100 - price_weight_pct} %"
    )

else:
    (
        price_weight,
        time_weight,
    ) = PROFILE_WEIGHTS[
        profile_option
    ]

    st.sidebar.caption(
        f"Precio: {price_weight:.0%} · "
        f"Tiempo: {time_weight:.0%}"
    )

reference_area_m2 = (
    st.sidebar.slider(
        "Superficie de referencia (m²)",
        min_value=30,
        max_value=150,
        value=80,
        step=5,
        help=(
            "Se utiliza únicamente para mostrar un precio territorial "
            "orientativo: €/m² × superficie. No es una valoración "
            "de una vivienda concreta."
        ),
    )
)

k_neighbors = (
    st.sidebar.slider(
        "Alternativas similares (KNN)",
        min_value=1,
        max_value=10,
        value=5,
        step=1,
    )
)


# ============================================================
# 7. GRUPO DESTINO × MODO Y RESTRICCIONES
# ============================================================

group_df = (
    work.loc[
        work[
            "destination_id"
        ].astype(str).eq(
            str(
                selected_destination_id
            )
        )
        & work[
            "transport_mode"
        ].eq(
            selected_mode
        )
    ]
    .copy()
)

if group_df.empty:
    st.warning(
        "No existen alternativas para la combinación "
        "destino × modo seleccionada."
    )
    st.stop()

st.sidebar.divider()
st.sidebar.subheader(
    "Restricciones opcionales"
)

use_price_limit = (
    st.sidebar.checkbox(
        "Limitar precio por m²"
    )
)

max_price_m2 = None

if use_price_limit:
    price_min = float(
        group_df[
            PRICE_COLUMN
        ].min()
    )
    price_max = float(
        group_df[
            PRICE_COLUMN
        ].max()
    )

    max_price_m2 = (
        st.sidebar.slider(
            "Precio máximo (€/m²)",
            min_value=int(
                np.floor(
                    price_min
                )
            ),
            max_value=int(
                np.ceil(
                    price_max
                )
            ),
            value=int(
                np.ceil(
                    price_max
                )
            ),
            step=max(
                1,
                int(
                    (
                        price_max
                        - price_min
                    )
                    / 50
                ),
            ),
        )
    )

use_budget_limit = (
    st.sidebar.checkbox(
        "Limitar presupuesto orientativo"
    )
)

max_reference_budget = None

if use_budget_limit:
    estimated_prices = (
        group_df[
            PRICE_COLUMN
        ]
        * float(
            reference_area_m2
        )
    )

    budget_min = int(
        np.floor(
            estimated_prices.min()
            / 10000
        )
        * 10000
    )

    budget_max = int(
        np.ceil(
            estimated_prices.max()
            / 10000
        )
        * 10000
    )

    if budget_min == budget_max:
        budget_max = (
            budget_min
            + 10000
        )

    max_reference_budget = (
        st.sidebar.slider(
            "Presupuesto máximo orientativo (€)",
            min_value=budget_min,
            max_value=budget_max,
            value=budget_max,
            step=10000,
        )
    )

use_time_limit = (
    st.sidebar.checkbox(
        "Limitar tiempo diario"
    )
)

max_time_minutes = None

if use_time_limit:
    time_min = float(
        group_df[
            TIME_COLUMN
        ].min()
    )
    time_max = float(
        group_df[
            TIME_COLUMN
        ].max()
    )

    max_time_minutes = (
        st.sidebar.slider(
            "Tiempo diario máximo (min)",
            min_value=int(
                np.floor(
                    time_min
                )
            ),
            max_value=int(
                np.ceil(
                    time_max
                )
            ),
            value=int(
                np.ceil(
                    time_max
                )
            ),
            step=1,
        )
    )

min_reliability = None

if (
    "price_reliability_score"
    in group_df.columns
    and group_df[
        "price_reliability_score"
    ].notna().any()
):
    use_reliability_limit = (
        st.sidebar.checkbox(
            "Exigir fiabilidad mínima del precio"
        )
    )

    if use_reliability_limit:
        reliability_values = (
            pd.to_numeric(
                group_df[
                    "price_reliability_score"
                ],
                errors="coerce",
            )
            .dropna()
        )

        reliability_min = float(
            reliability_values.min()
        )
        reliability_max = float(
            reliability_values.max()
        )

        min_reliability = (
            st.sidebar.slider(
                "Fiabilidad mínima",
                min_value=float(
                    np.floor(
                        reliability_min
                    )
                ),
                max_value=float(
                    np.ceil(
                        reliability_max
                    )
                ),
                value=float(
                    np.floor(
                        reliability_min
                    )
                ),
                step=1.0,
            )
        )


# ============================================================
# 8. APLICACIÓN DE RESTRICCIONES
# ============================================================

compatible = group_df.copy()

filter_audit = [
    {
        "Etapa": "Grupo destino × modo",
        "Alternativas": len(
            compatible
        ),
    }
]

if max_price_m2 is not None:
    compatible = (
        compatible.loc[
            compatible[
                PRICE_COLUMN
            ]
            <= float(
                max_price_m2
            )
            + TOLERANCE
        ]
        .copy()
    )

    filter_audit.append(
        {
            "Etapa": "Tras límite €/m²",
            "Alternativas": len(
                compatible
            ),
        }
    )

if max_reference_budget is not None:
    reference_price = (
        compatible[
            PRICE_COLUMN
        ]
        * float(
            reference_area_m2
        )
    )

    compatible = (
        compatible.loc[
            reference_price
            <= float(
                max_reference_budget
            )
            + TOLERANCE
        ]
        .copy()
    )

    filter_audit.append(
        {
            "Etapa": "Tras presupuesto orientativo",
            "Alternativas": len(
                compatible
            ),
        }
    )

if max_time_minutes is not None:
    compatible = (
        compatible.loc[
            compatible[
                TIME_COLUMN
            ]
            <= float(
                max_time_minutes
            )
            + TOLERANCE
        ]
        .copy()
    )

    filter_audit.append(
        {
            "Etapa": "Tras límite de tiempo",
            "Alternativas": len(
                compatible
            ),
        }
    )

if (
    min_reliability
    is not None
):
    compatible = (
        compatible.loc[
            compatible[
                "price_reliability_score"
            ]
            .fillna(-np.inf)
            >= float(
                min_reliability
            )
            - TOLERANCE
        ]
        .copy()
    )

    filter_audit.append(
        {
            "Etapa": "Tras fiabilidad mínima",
            "Alternativas": len(
                compatible
            ),
        }
    )

if compatible.empty:
    st.warning(
        "No existen barrios que cumplan simultáneamente "
        "las restricciones seleccionadas. "
        "Prueba a relajar alguno de los límites."
    )

    st.dataframe(
        pd.DataFrame(
            filter_audit
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.stop()


# ============================================================
# 9. RECOMENDACIÓN PRINCIPAL
# ============================================================

try:
    anchor, compatible_scored = (
        select_recommendation(
            compatible=compatible,
            price_weight=price_weight,
            time_weight=time_weight,
        )
    )
except Exception as exc:
    st.error(
        "No se ha podido calcular la recomendación."
    )
    st.exception(exc)
    st.stop()

anchor_zone_key = str(
    anchor[
        "zone_key"
    ]
)

pareto_compatible = (
    compatible_scored.loc[
        compatible_scored[
            "is_pareto_app"
        ]
    ]
    .copy()
)

estimated_reference_price = (
    float(
        anchor[
            PRICE_COLUMN
        ]
    )
    * float(
        reference_area_m2
    )
)


# ============================================================
# 10. RESULTADO PRINCIPAL
# ============================================================

st.subheader(
    "Recomendación principal"
)

st.caption(
    f"{MODE_ICONS[selected_mode]} "
    f"{selected_destination_name} · "
    f"{selected_mode_label}"
)

district_text = (
    str(
        anchor[
            "district_name"
        ]
    )
    if pd.notna(
        anchor[
            "district_name"
        ]
    )
    else "Distrito no disponible"
)

st.markdown(
    f"## {anchor['neighborhood_name']}"
)

st.write(
    f"**Distrito:** {district_text}"
)

metric_1, metric_2, metric_3, metric_4 = (
    st.columns(4)
)

metric_1.metric(
    "Precio de referencia",
    (
        f"{format_number(anchor[PRICE_COLUMN], 0)} €/m²"
    ),
)

metric_2.metric(
    "Desplazamiento diario",
    (
        f"{format_number(anchor[TIME_COLUMN], 1)} min"
    ),
)

metric_3.metric(
    f"Referencia {reference_area_m2} m²",
    (
        f"{format_number(estimated_reference_price, 0)} €"
    ),
)

metric_4.metric(
    "Puntuación de preferencia",
    (
        format_number(
            anchor[
                "preference_score_app"
            ],
            3,
        )
    ),
    help=(
        "Cuanto menor es la puntuación, mejor encaja "
        "la alternativa con los pesos seleccionados. "
        "La escala solo tiene sentido dentro del grupo destino × modo."
    ),
)

cheapest = (
    compatible_scored.sort_values(
        [
            PRICE_COLUMN,
            TIME_COLUMN,
            "zone_key",
        ]
    )
    .iloc[0]
)

fastest = (
    compatible_scored.sort_values(
        [
            TIME_COLUMN,
            PRICE_COLUMN,
            "zone_key",
        ]
    )
    .iloc[0]
)

price_vs_cheapest = (
    safe_percentage_difference(
        float(
            anchor[
                PRICE_COLUMN
            ]
        ),
        float(
            cheapest[
                PRICE_COLUMN
            ]
        ),
    )
)

time_vs_fastest = (
    safe_percentage_difference(
        float(
            anchor[
                TIME_COLUMN
            ]
        ),
        float(
            fastest[
                TIME_COLUMN
            ]
        ),
    )
)

group_price_median = float(
    group_df[
        PRICE_COLUMN
    ].median()
)

group_time_median = float(
    group_df[
        TIME_COLUMN
    ].median()
)

price_vs_group_median = (
    safe_percentage_difference(
        float(
            anchor[
                PRICE_COLUMN
            ]
        ),
        group_price_median,
    )
)

time_vs_group_median = (
    safe_percentage_difference(
        float(
            anchor[
                TIME_COLUMN
            ]
        ),
        group_time_median,
    )
)

priority_text = (
    profile_priority_text(
        price_weight,
        time_weight,
    )
)

explanation_parts = [
    (
        f"El perfil seleccionado **{priority_text}** "
        f"({price_weight:.0%} precio y {time_weight:.0%} tiempo)."
    ),
    (
        "La recomendación pertenece a la **frontera de Pareto "
        "del conjunto compatible**, por lo que no existe otro barrio "
        "que la mejore simultáneamente en precio y tiempo dentro de "
        "las restricciones activas."
    ),
]

if np.isfinite(
    price_vs_cheapest
):
    explanation_parts.append(
        "Frente al barrio compatible de menor precio, "
        f"su precio por m² es un **{price_vs_cheapest:+.1f} %** diferente."
    )

if np.isfinite(
    time_vs_fastest
):
    explanation_parts.append(
        "Frente al barrio compatible con menor tiempo, "
        f"su desplazamiento diario es un **{time_vs_fastest:+.1f} %** diferente."
    )

if np.isfinite(
    price_vs_group_median
):
    explanation_parts.append(
        "Respecto a la mediana del grupo destino–modo completo, "
        f"el precio se sitúa en **{price_vs_group_median:+.1f} %**."
    )

if np.isfinite(
    time_vs_group_median
):
    explanation_parts.append(
        "Respecto a la mediana del grupo destino–modo completo, "
        f"el tiempo se sitúa en **{time_vs_group_median:+.1f} %**."
    )

st.markdown(
    " ".join(
        explanation_parts
    )
)

if (
    "price_reliability_score"
    in anchor.index
    and pd.notna(
        anchor[
            "price_reliability_score"
        ]
    )
):
    reliability_text = (
        f"**Fiabilidad del precio:** "
        f"{format_number(anchor['price_reliability_score'], 1)}"
    )

    if (
        "price_reliability_level"
        in anchor.index
        and pd.notna(
            anchor[
                "price_reliability_level"
            ]
        )
    ):
        reliability_text += (
            f" · {anchor['price_reliability_level']}"
        )

    st.info(
        reliability_text
    )


# ============================================================
# 11. INFORMACIÓN COMPLEMENTARIA
# ============================================================

detail_rows = []

for label, candidates in (
    OPTIONAL_DISPLAY_COLUMNS.items()
):
    column = (
        first_existing_column(
            compatible_scored,
            candidates,
        )
    )

    if (
        column is None
        or column not in anchor.index
        or pd.isna(
            anchor[
                column
            ]
        )
    ):
        continue

    value = anchor[
        column
    ]

    if label in {
        "Fiabilidad del precio",
        "Tiempo andando diario (min)",
        "Tiempo de espera diario (min)",
        "Transbordos diarios",
        "Distancia diaria (m)",
    }:
        value = format_number(
            value,
            1,
        )

    detail_rows.append(
        {
            "Indicador": label,
            "Valor": value,
        }
    )

if detail_rows:
    with st.expander(
        "Detalles adicionales de la alternativa"
    ):
        st.dataframe(
            pd.DataFrame(
                detail_rows
            ),
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# 12. ALTERNATIVAS PARETO + KNN
# ============================================================

try:
    neighbors = (
        find_pareto_neighbors(
            compatible=compatible_scored,
            anchor_zone_key=anchor_zone_key,
            feature_columns=KNN_FEATURES,
            k=k_neighbors,
        )
    )
except Exception as exc:
    st.warning(
        "La recomendación principal se ha calculado, "
        "pero no ha sido posible obtener alternativas KNN."
    )
    st.exception(exc)
    neighbors = pd.DataFrame()

st.subheader(
    "Alternativas similares"
)

st.caption(
    "KNN busca barrios similares dentro de la frontera de Pareto "
    "del conjunto compatible y siempre dentro del mismo destino y modo. "
    "La distancia es una medida de similitud en el espacio estandarizado, "
    "no una distancia geográfica."
)

if neighbors.empty:
    st.info(
        "No hay suficientes alternativas Pareto distintas "
        "de la recomendación principal para mostrar vecinos."
    )
else:
    neighbors_display = pd.DataFrame(
        {
            "Posición": (
                neighbors[
                    "knn_rank_app"
                ]
                .astype(int)
            ),
            "Barrio": (
                neighbors[
                    "neighborhood_name"
                ]
                .astype(str)
            ),
            "Distrito": (
                neighbors[
                    "district_name"
                ]
                .astype(str)
            ),
            "Precio (€/m²)": (
                neighbors[
                    PRICE_COLUMN
                ]
                .astype(float)
                .round(0)
            ),
            "Tiempo diario (min)": (
                neighbors[
                    TIME_COLUMN
                ]
                .astype(float)
                .round(1)
            ),
            "Distancia KNN normalizada": (
                neighbors[
                    "knn_distance_normalized_app"
                ]
                .astype(float)
                .round(3)
            ),
        }
    )

    if (
        "price_reliability_score"
        in neighbors.columns
        and neighbors[
            "price_reliability_score"
        ].notna().any()
    ):
        neighbors_display[
            "Fiabilidad"
        ] = (
            pd.to_numeric(
                neighbors[
                    "price_reliability_score"
                ],
                errors="coerce",
            )
            .round(1)
            .values
        )

    st.dataframe(
        neighbors_display,
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# 13. GRÁFICO PRECIO–TIEMPO
# ============================================================

st.subheader(
    "Equilibrio entre precio y desplazamiento"
)

fig, ax = plt.subplots(
    figsize=(9, 6)
)

ax.scatter(
    compatible_scored[
        PRICE_COLUMN
    ],
    compatible_scored[
        TIME_COLUMN
    ],
    alpha=0.35,
    label="Barrios compatibles",
)

front = (
    pareto_compatible.sort_values(
        [
            PRICE_COLUMN,
            TIME_COLUMN,
        ]
    )
)

ax.scatter(
    front[
        PRICE_COLUMN
    ],
    front[
        TIME_COLUMN
    ],
    s=70,
    label="Frontera de Pareto",
)

if len(front) > 1:
    ax.plot(
        front[
            PRICE_COLUMN
        ],
        front[
            TIME_COLUMN
        ],
        linewidth=1.2,
        alpha=0.6,
    )

ax.scatter(
    [
        anchor[
            PRICE_COLUMN
        ]
    ],
    [
        anchor[
            TIME_COLUMN
        ]
    ],
    marker="*",
    s=250,
    label="Recomendación",
)

if not neighbors.empty:
    ax.scatter(
        neighbors[
            PRICE_COLUMN
        ],
        neighbors[
            TIME_COLUMN
        ],
        marker="x",
        s=90,
        label="Alternativas KNN",
    )

ax.annotate(
    str(
        anchor[
            "neighborhood_name"
        ]
    ),
    (
        float(
            anchor[
                PRICE_COLUMN
            ]
        ),
        float(
            anchor[
                TIME_COLUMN
            ]
        ),
    ),
    xytext=(7, 7),
    textcoords="offset points",
)

ax.set_xlabel(
    "Precio de referencia (€/m²)"
)

ax.set_ylabel(
    "Tiempo diario de desplazamiento (min)"
)

ax.set_title(
    f"{selected_destination_name} · "
    f"{selected_mode_label}"
)

ax.grid(
    alpha=0.25
)

ax.legend()

fig.tight_layout()

st.pyplot(
    fig,
    use_container_width=True,
)

plt.close(fig)


# ============================================================
# 14. MAPA OPCIONAL
# ============================================================

latitude_column = (
    first_existing_column(
        compatible_scored,
        [
            "latitude",
            "lat",
            "neighborhood_latitude",
        ],
    )
)

longitude_column = (
    first_existing_column(
        compatible_scored,
        [
            "longitude",
            "lon",
            "lng",
            "neighborhood_longitude",
        ],
    )
)

if (
    latitude_column is not None
    and longitude_column is not None
):
    map_rows = (
        compatible_scored[
            [
                latitude_column,
                longitude_column,
            ]
        ]
        .copy()
    )

    map_rows[
        latitude_column
    ] = pd.to_numeric(
        map_rows[
            latitude_column
        ],
        errors="coerce",
    )

    map_rows[
        longitude_column
    ] = pd.to_numeric(
        map_rows[
            longitude_column
        ],
        errors="coerce",
    )

    map_rows = (
        map_rows.dropna(
            subset=[
                latitude_column,
                longitude_column,
            ]
        )
    )

    if not map_rows.empty:
        st.subheader(
            "Localización de los barrios compatibles"
        )

        map_display = (
            map_rows.rename(
                columns={
                    latitude_column: "lat",
                    longitude_column: "lon",
                }
            )
        )

        st.map(
            map_display[
                [
                    "lat",
                    "lon",
                ]
            ]
        )


# ============================================================
# 15. EXPLICABILIDAD Y AUDITORÍA
# ============================================================

with st.expander(
    "Cómo se ha calculado la recomendación"
):
    st.markdown(
        f"""
**Grupo analizado**

- Destino: **{selected_destination_name}**
- Modo: **{selected_mode_label}**
- Peso del precio: **{price_weight:.0%}**
- Peso del tiempo: **{time_weight:.0%}**

**Proceso**

1. Se selecciona exclusivamente la combinación **destino × modo**.
2. Se aplican las restricciones duras elegidas por el usuario.
3. Se recalcula la frontera de Pareto sobre las alternativas compatibles.
4. La puntuación se calcula con `price_normalized` y `time_normalized`
   ya fijadas por el notebook 08 para el grupo completo, por lo que aplicar
   filtros no cambia artificialmente la escala de referencia.
5. Se selecciona la alternativa Pareto con menor puntuación ponderada.
6. La fiabilidad inmobiliaria, cuando existe, funciona como filtro opcional
   y desempate secundario; no sustituye los objetivos precio–tiempo.
7. KNN busca alternativas similares dentro de la frontera Pareto compatible,
   usando variables estandarizadas dentro de esta misma combinación
   destino × modo.

**Puntuación**

`score = peso_precio × precio_normalizado + peso_tiempo × tiempo_normalizado`

Cuanto menor es la puntuación, mejor encaja la alternativa con las
preferencias seleccionadas.
"""
    )

with st.expander(
    "Cobertura y auditoría"
):
    coverage_1, coverage_2, coverage_3, coverage_4 = (
        st.columns(4)
    )

    coverage_1.metric(
        "Alternativas del grupo",
        len(
            group_df
        ),
    )

    coverage_2.metric(
        "Compatibles",
        len(
            compatible_scored
        ),
    )

    coverage_3.metric(
        "Pareto compatibles",
        int(
            compatible_scored[
                "is_pareto_app"
            ].sum()
        ),
    )

    coverage_4.metric(
        "Variables KNN",
        len(
            KNN_FEATURES
        ),
    )

    st.markdown(
        "**Auditoría de filtros**"
    )

    st.dataframe(
        pd.DataFrame(
            filter_audit
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown(
        "**Selección de variables auxiliares para KNN**"
    )

    feature_audit_display = (
        feature_audit.copy()
    )

    feature_audit_display[
        "Cobertura"
    ] = (
        100
        * feature_audit_display[
            "Cobertura"
        ]
    ).round(1)

    feature_audit_display = (
        feature_audit_display.rename(
            columns={
                "Cobertura": "Cobertura (%)",
            }
        )
    )

    st.dataframe(
        feature_audit_display,
        hide_index=True,
        use_container_width=True,
    )

    st.write(
        "**Variables utilizadas por KNN:** "
        + ", ".join(
            KNN_FEATURES
        )
    )

    st.write(
        "**Archivo de entrada:** "
        "`data/results/pareto_by_destination_mode.csv`"
    )


# ============================================================
# 16. LIMITACIONES
# ============================================================

with st.expander(
    "Limitaciones de interpretación"
):
    st.markdown(
        """
- El sistema recomienda **barrios agregados**, no viviendas concretas.
- Los precios son referencias territoriales por metro cuadrado y no
  valoraciones individualizadas.
- El precio orientativo de una superficie de referencia se obtiene mediante
  una multiplicación y no equivale al precio real de un inmueble concreto.
- Los tiempos dependen de la fecha, los horarios y la coordenada
  representativa utilizada para cada barrio.
- El coche no incorpora tráfico en tiempo real.
- Los recorridos a pie y en bicicleta dependen de la representación de la
  red en OpenStreetMap.
- Las rutas no disponibles no se imputan con tiempos inventados en el pipeline.
- El modo de transporte es una preferencia categórica y no un tercer objetivo
  de Pareto.
- KNN se utiliza como método de similitud basado en contenido; no existe
  historial de usuarios para realizar filtrado colaborativo.
"""
    )


# ============================================================
# 17. PIE
# ============================================================

st.divider()

st.caption(
    "TFG · Sistema de recomendación de barrios residenciales en Madrid · "
    "Pareto + personalización + extensión KNN multimodal."
)
