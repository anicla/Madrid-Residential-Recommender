from __future__ import annotations

import argparse
import math
import os
import time
import warnings
from datetime import datetime, timezone
from typing import Dict, Tuple

import numpy as np
import openrouteservice
import pandas as pd

REQUIRED_COLUMNS = {"zone_key", "destino", "modo", "tiempo_transporte_min", "fuente"}

# Approximate centroids for Madrid districts used as zone_key.
ZONE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "arganzuela": (40.3970, -3.6947),
    "barajas": (40.4700, -3.5770),
    "barrio-de-salamanca": (40.4277, -3.6830),
    "carabanchel": (40.3906, -3.7440),
    "centro": (40.4168, -3.7038),
    "chamartin": (40.4629, -3.6796),
    "chamberi": (40.4332, -3.7009),
    "ciudad-lineal": (40.4374, -3.6389),
    "fuencarral": (40.4875, -3.7165),
    "hortaleza": (40.4699, -3.6417),
    "latina": (40.4037, -3.7375),
    "moncloa": (40.4381, -3.7236),
    "moratalaz": (40.4078, -3.6450),
    "puente-de-vallecas": (40.3928, -3.6590),
    "retiro": (40.4132, -3.6763),
    "san-blas": (40.4385, -3.6133),
    "tetuan": (40.4592, -3.6996),
    "usera": (40.3874, -3.7010),
    "vicalvaro": (40.4026, -3.6048),
    "villa-de-vallecas": (40.3709, -3.6207),
    "villaverde": (40.3470, -3.7062),
}

# Main commute destinations suggested by the tutor.
DESTINATIONS: Dict[str, Tuple[float, float]] = {
    "sol": (40.4169, -3.7035),
    "cuatro_caminos": (40.4469, -3.7034),
    "las_tablas": (40.5069, -3.6696),
    "atocha": (40.4071, -3.6916),
    "plaza_espana": (40.4239, -3.7131),
    "chamartin": (40.4629, -3.6732),
    "retiro": (40.4132, -3.6763),
    "tribunal": (40.4318, -3.7051),
    "serrano": (40.4304, -3.6788),
    "campo_naciones": (40.4715, -3.6217),
    "alcala_castellana": (40.4555, -3.6877),
    "moncloa_universidad": (40.4519, -3.7286),
    "ferraz": (40.4299, -3.7220),
}

# ORS has no native public-transit profile. We keep this mapping explicit
# and mark it as a proxy in the source column.
MODE_TO_ORS_PROFILE = {
    "transporte_publico": "driving-car",
    "coche": "driving-car",
    "a_pie": "foot-walking",
    "bicicleta": "cycling-regular",
}

PROFILE_AVG_SPEED_KMH = {
    "driving-car": 24.0,
    "foot-walking": 4.8,
    "cycling-regular": 14.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fill accessibility_template.csv with travel time estimates using "
            "OpenRouteService."
        )
    )
    parser.add_argument(
        "--template",
        default="data/accessibility_template.csv",
        help="Path to accessibility template csv.",
    )
    parser.add_argument(
        "--output",
        default="data/accessibility_template_filled.csv",
        help="Output csv path.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("ORS_API_KEY"),
        help="OpenRouteService API key. Defaults to ORS_API_KEY env var.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute rows even if tiempo_transporte_min is already filled.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.2,
        help="Pause between API calls to avoid rate-limit bursts.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="Max retries when ORS returns rate-limit or transient errors.",
    )
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        default=8.0,
        help="Initial backoff wait in seconds. It grows exponentially per retry.",
    )
    return parser.parse_args()


def validate_template(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in template: {sorted(missing)}")


def auto_generate_template(path: str) -> pd.DataFrame:
    """Generate accessibility template from zone and destination centroids."""
    rows = []
    for zone_key in sorted(ZONE_CENTROIDS.keys()):
        for destination in sorted(DESTINATIONS.keys()):
            rows.append(
                {
                    "zone_key": zone_key,
                    "destino": destination,
                    "modo": "transporte_publico",
                    "tiempo_transporte_min": np.nan,
                    "fuente": "pendiente",
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"Generated template: {path} ({len(df)} rows)")
    return df


def route_minutes(
    client: openrouteservice.Client,
    origin_latlon: Tuple[float, float],
    dest_latlon: Tuple[float, float],
    profile: str,
    max_retries: int,
    backoff_seconds: float,
) -> float:
    if origin_latlon == dest_latlon:
        return 1.0

    # ORS expects [lon, lat].
    coordinates = [
        [origin_latlon[1], origin_latlon[0]],
        [dest_latlon[1], dest_latlon[0]],
    ]
    for attempt in range(max_retries + 1):
        try:
            result = client.directions(
                coordinates=coordinates,
                profile=profile,
                format="json",
            )
            if "routes" not in result or not result["routes"]:
                error_detail = result.get("error") or result.get("message") or result
                raise ValueError(f"ORS response without routes: {error_detail}")
            seconds = result["routes"][0]["summary"]["duration"]
            return float(seconds) / 60.0
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            is_rate_limited = (
                "429" in message
                or "rate limit" in message
                or "too many requests" in message
            )
            is_retryable = is_rate_limited or any(
                token in message
                for token in [
                    "timeout",
                    "temporar",
                    "connection",
                    "reset",
                    "remote end closed",
                    "server error",
                    "503",
                    "502",
                    "504",
                ]
            )
            if attempt >= max_retries:
                raise

            if not is_retryable:
                raise

            # For rate limit, wait longer and increase exponentially.
            if is_rate_limited:
                wait_seconds = max(backoff_seconds * (2**attempt), 1.0)
            else:
                wait_seconds = max(2.0 * (attempt + 1), 1.0)

            print(
                f"Retry {attempt + 1}/{max_retries} after {wait_seconds:.1f}s "
                f"({type(exc).__name__})"
            )
            time.sleep(wait_seconds)

    raise RuntimeError("Unreachable retry state in route_minutes")


def haversine_km(
    origin_latlon: Tuple[float, float],
    dest_latlon: Tuple[float, float],
) -> float:
    lat1, lon1 = origin_latlon
    lat2, lon2 = dest_latlon

    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def fallback_minutes(
    origin_latlon: Tuple[float, float],
    dest_latlon: Tuple[float, float],
    profile: str,
) -> float:
    distance_km = haversine_km(origin_latlon, dest_latlon)
    detour_factor = 1.35
    speed_kmh = PROFILE_AVG_SPEED_KMH.get(profile, 22.0)
    estimated_minutes = (distance_km * detour_factor / speed_kmh) * 60.0
    return max(estimated_minutes, 1.0)


def fill_accessibility_times(
    df: pd.DataFrame,
    client: openrouteservice.Client,
    overwrite: bool,
    sleep_seconds: float,
    max_retries: int,
    backoff_seconds: float,
) -> pd.DataFrame:
    out = df.copy()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    unresolved_rows = []
    for idx, row in out.iterrows():
        current_time = row.get("tiempo_transporte_min")
        if (not overwrite) and pd.notna(current_time):
            continue

        zone_key = str(row["zone_key"]).strip().lower()
        destino = str(row["destino"]).strip().lower()
        modo = str(row["modo"]).strip().lower()

        origin = ZONE_CENTROIDS.get(zone_key)
        dest = DESTINATIONS.get(destino)
        profile = MODE_TO_ORS_PROFILE.get(modo, "driving-car")

        if origin is None or dest is None:
            unresolved_rows.append(idx)
            out.at[idx, "fuente"] = f"error: coordenadas_no_disponibles:{generated_at}"
            continue

        try:
            minutes = route_minutes(
                client,
                origin,
                dest,
                profile=profile,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            out.at[idx, "tiempo_transporte_min"] = round(minutes, 2)
            proxy_tag = "_proxy" if modo == "transporte_publico" else ""
            out.at[idx, "fuente"] = f"openrouteservice:{profile}{proxy_tag}:{generated_at}"
        except Exception as exc:  # noqa: BLE001
            estimated = fallback_minutes(origin, dest, profile=profile)
            out.at[idx, "tiempo_transporte_min"] = round(estimated, 2)
            out.at[idx, "fuente"] = (
                f"fallback_haversine:{profile}:{type(exc).__name__}:{generated_at}"
            )
            print(
                f"Fallback used for {zone_key}->{destino} ({type(exc).__name__}), "
                f"minutes={estimated:.2f}"
            )

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if unresolved_rows:
        print(f"Rows unresolved: {len(unresolved_rows)}")
    else:
        print("All rows resolved successfully.")

    return out


def main() -> None:
    args = parse_args()

    warnings.filterwarnings(
        "ignore",
        message="Rate limit exceeded.*",
        category=UserWarning,
    )

    if not args.api_key:
        raise ValueError(
            "Missing ORS API key. Use --api-key or define ORS_API_KEY in env."
        )

    if not os.path.exists(args.template):
        print(f"Template not found: {args.template}")
        template = auto_generate_template(args.template)
    else:
        template = pd.read_csv(args.template)
    validate_template(template)

    client = openrouteservice.Client(key=args.api_key)
    filled = fill_accessibility_times(
        template,
        client=client,
        overwrite=args.overwrite,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
    )

    filled.to_csv(args.output, index=False)
    print(f"Saved: {args.output}")

    # Quick quality checks printed for notebook/log usage.
    filled_count = int(filled["tiempo_transporte_min"].notna().sum())
    total_count = int(len(filled))
    print(f"Filled travel times: {filled_count}/{total_count}")

    summary = (
        filled.dropna(subset=["tiempo_transporte_min"])
        .groupby("destino", as_index=False)["tiempo_transporte_min"]
        .agg(["mean", "median", "min", "max"])
    )
    if not summary.empty:
        print("Summary by destination (minutes):")
        print(summary)


if __name__ == "__main__":
    main()
