from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


REQUIRED_ZONE_COLUMNS = {
    "zone_key",
    "precio_media",
    "precio_m2_media",
    "metros_media",
    "habitaciones_media",
    "banos_media",
    "ascensor_ratio",
    "exterior_ratio",
}

REQUIRED_ACCESSIBILITY_COLUMNS = {
    "zone_key",
    "destino",
    "tiempo_transporte_min",
}


@dataclass(frozen=True)
class UserProfile:
    name: str
    max_budget: float
    target_commute_min: float
    preferred_size_m2: float
    weight_price: float = 0.35
    weight_commute: float = 0.4
    weight_size: float = 0.15
    weight_exterior: float = 0.05
    weight_elevator: float = 0.05


DEFAULT_PROFILES = {
    "estudiante_centro": UserProfile(
        name="Estudiante con presupuesto bajo y trabajo en el centro",
        max_budget=350_000,
        target_commute_min=35,
        preferred_size_m2=55,
        weight_price=0.4,
        weight_commute=0.4,
        weight_size=0.1,
        weight_exterior=0.05,
        weight_elevator=0.05,
    ),
    "profesional_periferia": UserProfile(
        name="Profesional con presupuesto alto y prioridad por espacio",
        max_budget=850_000,
        target_commute_min=50,
        preferred_size_m2=120,
        weight_price=0.2,
        weight_commute=0.2,
        weight_size=0.45,
        weight_exterior=0.1,
        weight_elevator=0.05,
    ),
    "familia_equilibrada": UserProfile(
        name="Familia que busca equilibrio entre espacio y acceso",
        max_budget=600_000,
        target_commute_min=40,
        preferred_size_m2=95,
        weight_price=0.3,
        weight_commute=0.3,
        weight_size=0.25,
        weight_exterior=0.1,
        weight_elevator=0.05,
    ),
}


def load_zone_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_ZONE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en el dataset de zonas: {sorted(missing)}")
    return df.copy()


def load_accessibility_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_ACCESSIBILITY_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Faltan columnas en el dataset de accesibilidad: {sorted(missing)}"
        )
    return df.copy()


def attach_accessibility_features(
    zone_df: pd.DataFrame,
    accessibility_df: pd.DataFrame,
    destination_col: str = "destino",
    time_col: str = "tiempo_transporte_min",
) -> pd.DataFrame:
    pivot = accessibility_df.pivot_table(
        index="zone_key",
        columns=destination_col,
        values=time_col,
        aggfunc="mean",
    )
    pivot = pivot.add_prefix("tt_").reset_index()
    merged = zone_df.merge(pivot, on="zone_key", how="left")
    return merged


def build_accessibility_template(
    zone_keys: Iterable[str],
    destinations: Iterable[str],
) -> pd.DataFrame:
    rows = []
    for zone_key in zone_keys:
        for destination in destinations:
            rows.append(
                {
                    "zone_key": zone_key,
                    "destino": destination,
                    "modo": "transporte_publico",
                    "tiempo_transporte_min": np.nan,
                    "fuente": "pendiente",
                }
            )
    return pd.DataFrame(rows)


def compute_pareto_front(
    df: pd.DataFrame,
    price_col: str = "precio_media",
    time_col: str = "tt_sol",
) -> pd.DataFrame:
    if time_col not in df.columns:
        raise ValueError(f"No existe la columna de tiempo '{time_col}' en el dataframe.")

    work = df[[c for c in df.columns]].copy()
    work = work.dropna(subset=[price_col, time_col]).reset_index(drop=True)

    prices = work[price_col].to_numpy()
    times = work[time_col].to_numpy()
    is_dominated = np.zeros(len(work), dtype=bool)

    for i in range(len(work)):
        dominates_i = (
            (prices <= prices[i])
            & (times <= times[i])
            & ((prices < prices[i]) | (times < times[i]))
        )
        dominates_i[i] = False
        if dominates_i.any():
            is_dominated[i] = True

    work["pareto_optima"] = ~is_dominated
    return work.sort_values([time_col, price_col]).reset_index(drop=True)


def utility_score(
    df: pd.DataFrame,
    profile: UserProfile,
    time_col: str,
    price_col: str = "precio_media",
    size_col: str = "metros_media",
) -> pd.Series:
    for col in [price_col, size_col, time_col, "exterior_ratio", "ascensor_ratio"]:
        if col not in df.columns:
            raise ValueError(f"No existe la columna requerida '{col}'.")

    price_penalty = np.clip(df[price_col] / profile.max_budget, 0, None)
    commute_penalty = np.clip(df[time_col] / profile.target_commute_min, 0, None)
    size_reward = np.clip(df[size_col] / profile.preferred_size_m2, 0, 2)

    return (
        -profile.weight_price * price_penalty
        - profile.weight_commute * commute_penalty
        + profile.weight_size * size_reward
        + profile.weight_exterior * df["exterior_ratio"].fillna(0)
        + profile.weight_elevator * df["ascensor_ratio"].fillna(0)
    )


def rank_zones_for_profile(
    df: pd.DataFrame,
    profile: UserProfile,
    time_col: str = "tt_sol",
    top_n: int = 5,
) -> pd.DataFrame:
    work = df.copy()
    work["utility_score"] = utility_score(work, profile=profile, time_col=time_col)
    work["within_budget"] = work["precio_media"] <= profile.max_budget
    work["within_commute"] = work[time_col] <= profile.target_commute_min
    work["size_gap_m2"] = work["metros_media"] - profile.preferred_size_m2

    return work.sort_values(
        ["within_budget", "within_commute", "utility_score"],
        ascending=[False, False, False],
    ).head(top_n)


def hybrid_knn_recommendation(
    df: pd.DataFrame,
    user_preferences: dict,
    time_col: str = "tt_sol",
    n_neighbors: int = 5,
) -> pd.DataFrame:
    feature_cols = [
        "precio_media",
        "metros_media",
        "habitaciones_media",
        "banos_media",
        "ascensor_ratio",
        "exterior_ratio",
        time_col,
    ]
    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas necesarias para KNN híbrido: {missing}")

    work = df.dropna(subset=feature_cols).copy()
    if work.empty:
        raise ValueError("No hay suficientes datos tras eliminar filas con nulos.")

    scaler = StandardScaler()
    X = scaler.fit_transform(work[feature_cols])

    neigh = NearestNeighbors(n_neighbors=min(n_neighbors, len(work)))
    neigh.fit(X)

    user_vector = pd.DataFrame(
        [
            {
                "precio_media": user_preferences["precio_objetivo"],
                "metros_media": user_preferences["metros_objetivo"],
                "habitaciones_media": user_preferences["habitaciones_objetivo"],
                "banos_media": user_preferences["banos_objetivo"],
                "ascensor_ratio": user_preferences.get("ascensor_ratio_objetivo", 0.5),
                "exterior_ratio": user_preferences.get("exterior_ratio_objetivo", 0.5),
                time_col: user_preferences["tiempo_objetivo_min"],
            }
        ]
    )
    user_scaled = scaler.transform(user_vector[feature_cols])
    distances, indices = neigh.kneighbors(user_scaled)

    result = work.iloc[indices[0]].copy()
    result["knn_distance"] = distances[0]

    profile = UserProfile(
        name="perfil_ad_hoc",
        max_budget=user_preferences["precio_objetivo"],
        target_commute_min=user_preferences["tiempo_objetivo_min"],
        preferred_size_m2=user_preferences["metros_objetivo"],
        weight_price=user_preferences.get("weight_price", 0.35),
        weight_commute=user_preferences.get("weight_commute", 0.4),
        weight_size=user_preferences.get("weight_size", 0.15),
        weight_exterior=user_preferences.get("weight_exterior", 0.05),
        weight_elevator=user_preferences.get("weight_elevator", 0.05),
    )
    result["utility_score"] = utility_score(result, profile=profile, time_col=time_col)

    return result.sort_values(["utility_score", "knn_distance"], ascending=[False, True])
