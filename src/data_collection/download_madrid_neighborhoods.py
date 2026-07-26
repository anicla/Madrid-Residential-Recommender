from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests


# ---------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "official"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

ZIP_PATH = RAW_DIR / "madrid_barrios_shp.zip"
EXTRACT_DIR = RAW_DIR / "madrid_barrios_shp"

ZONES_CSV_PATH = PROCESSED_DIR / "zones_master.csv"
ZONES_GEOJSON_PATH = PROCESSED_DIR / "zones_master.geojson"
METADATA_PATH = RAW_DIR / "madrid_barrios_metadata.json"


# Recurso oficial del Ayuntamiento de Madrid
DOWNLOAD_URL = (
    "https://datos.madrid.es/dataset/300496-0-barrios-madrid/"
    "resource/300496-3-barrios-madrid/download/"
    "300496-3-barrios-madrid.zip"
)

SOURCE_PAGE = (
    "https://datos.madrid.es/dataset/300496-0-barrios-madrid"
)


def create_directories() -> None:
    """Crea las carpetas necesarias si todavía no existen."""
    for directory in [
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        EXTRACT_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def calculate_sha256(file_path: Path) -> str:
    """Calcula la huella SHA-256 del archivo descargado."""
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def download_file() -> None:
    """Descarga el ZIP oficial si todavía no está disponible."""
    print("Descargando barrios oficiales de Madrid...")

    response = requests.get(
        DOWNLOAD_URL,
        timeout=120,
        headers={
            "User-Agent": (
                "TFG-Recomendador-Viviendas/"
                "1.0 academic-use"
            )
        },
    )
    response.raise_for_status()

    with ZIP_PATH.open("wb") as file:
        file.write(response.content)

    print(f"Archivo descargado en: {ZIP_PATH}")


def extract_zip() -> None:
    """Extrae el archivo ZIP."""
    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "r") as zip_file:
        zip_file.extractall(EXTRACT_DIR)

    print(f"Archivo extraído en: {EXTRACT_DIR}")


def find_shapefile() -> Path:
    """Localiza el archivo .shp dentro del ZIP extraído."""
    shapefiles = list(EXTRACT_DIR.rglob("*.shp"))

    if not shapefiles:
        raise FileNotFoundError(
            "No se encontró ningún archivo SHP en el ZIP."
        )

    if len(shapefiles) > 1:
        print("Se encontraron varios SHP:")
        for path in shapefiles:
            print(f"  - {path}")

    return shapefiles[0]


def normalize_column_names(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Renombra las columnas oficiales a nombres claros y estables.

    Los nombres del recurso pueden variar ligeramente entre versiones,
    por lo que se comprueba que existan antes de renombrarlos.
    """
    rename_map = {
        "CODDIS": "district_code",
        "NOMDIS": "district_name",
        "COD_BAR": "neighborhood_code",
        "NOMBRE": "neighborhood_name",
        "NUM_BAR": "neighborhood_number",
    }

    available_renames = {
        original: new
        for original, new in rename_map.items()
        if original in gdf.columns
    }

    gdf = gdf.rename(columns=available_renames)

    required_columns = [
        "district_code",
        "district_name",
        "neighborhood_code",
        "neighborhood_name",
        "geometry",
    ]

    missing = [
        column
        for column in required_columns
        if column not in gdf.columns
    ]

    if missing:
        raise ValueError(
            "Faltan columnas obligatorias en el SHP: "
            f"{missing}. Columnas disponibles: {list(gdf.columns)}"
        )

    return gdf


def clean_text(series: pd.Series) -> pd.Series:
    """Limpia espacios y homogeneiza el texto."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def build_zones_master(
    shapefile_path: Path,
) -> gpd.GeoDataFrame:
    """Construye la tabla maestra oficial de barrios."""
    print(f"Leyendo: {shapefile_path}")

    neighborhoods = gpd.read_file(shapefile_path)
    neighborhoods = normalize_column_names(neighborhoods)

    # Conservamos los códigos como texto para no perder ceros iniciales.
    neighborhoods["district_code"] = (
        neighborhoods["district_code"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(2)
    )

    neighborhoods["neighborhood_code"] = (
        neighborhoods["neighborhood_code"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(3)
    )

    neighborhoods["district_name"] = clean_text(
        neighborhoods["district_name"]
    )

    neighborhoods["neighborhood_name"] = clean_text(
        neighborhoods["neighborhood_name"]
    )

    # Identificador estable que utilizaremos en todas las tablas.
    neighborhoods["zone_key"] = (
        "MAD-"
        + neighborhoods["neighborhood_code"]
    )

    # La geometría oficial debe tener un CRS definido.
    if neighborhoods.crs is None:
        raise ValueError(
            "El archivo geográfico no contiene un sistema "
            "de referencia de coordenadas."
        )

    # Calculamos un punto representativo dentro de cada polígono.
    # Es preferible al centroide porque garantiza que el punto
    # se encuentre dentro del barrio.
    projected = neighborhoods.to_crs(epsg=25830)
    representative_points = projected.geometry.representative_point()
    representative_points = representative_points.to_crs(epsg=4326)

    neighborhoods["latitude"] = representative_points.y
    neighborhoods["longitude"] = representative_points.x

    # Área oficial calculada en km².
    neighborhoods["area_km2"] = (
        projected.geometry.area / 1_000_000
    )

    # Guardamos la geometría final en WGS84.
    neighborhoods = neighborhoods.to_crs(epsg=4326)

    selected_columns = [
        "zone_key",
        "neighborhood_code",
        "neighborhood_name",
        "district_code",
        "district_name",
        "latitude",
        "longitude",
        "area_km2",
        "geometry",
    ]

    neighborhoods = neighborhoods[selected_columns].copy()

    neighborhoods = neighborhoods.sort_values(
        ["district_code", "neighborhood_code"]
    ).reset_index(drop=True)

    return neighborhoods


def validate_zones(
    neighborhoods: gpd.GeoDataFrame,
) -> None:
    """Comprueba la calidad mínima de la tabla territorial."""
    print("\nValidación de la tabla territorial")
    print("----------------------------------")
    print(f"Número de barrios: {len(neighborhoods)}")
    print(
        "Número de distritos:",
        neighborhoods["district_code"].nunique(),
    )
    print(
        "Códigos de barrio duplicados:",
        neighborhoods["neighborhood_code"].duplicated().sum(),
    )
    print(
        "Zone keys duplicadas:",
        neighborhoods["zone_key"].duplicated().sum(),
    )
    print(
        "Geometrías ausentes:",
        neighborhoods.geometry.isna().sum(),
    )
    print(
        "Geometrías inválidas:",
        (~neighborhoods.geometry.is_valid).sum(),
    )
    print(
        "Coordenadas ausentes:",
        neighborhoods[
            ["latitude", "longitude"]
        ].isna().any(axis=1).sum(),
    )

    if len(neighborhoods) != 131:
        raise ValueError(
            "Se esperaban 131 barrios oficiales, "
            f"pero se han encontrado {len(neighborhoods)}."
        )

    if neighborhoods["district_code"].nunique() != 21:
        raise ValueError(
            "Se esperaban 21 distritos oficiales."
        )

    if neighborhoods["zone_key"].duplicated().any():
        raise ValueError(
            "Se han encontrado identificadores zone_key duplicados."
        )

    if neighborhoods.geometry.isna().any():
        raise ValueError(
            "Hay barrios sin geometría."
        )


def save_outputs(
    neighborhoods: gpd.GeoDataFrame,
) -> None:
    """Guarda la tabla territorial en CSV y GeoJSON."""
    csv_data = neighborhoods.drop(columns="geometry")

    csv_data.to_csv(
        ZONES_CSV_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    neighborhoods.to_file(
        ZONES_GEOJSON_PATH,
        driver="GeoJSON",
    )

    metadata = {
        "dataset_name": "Barrios municipales de Madrid",
        "publisher": "Ayuntamiento de Madrid",
        "source_page": SOURCE_PAGE,
        "download_url": DOWNLOAD_URL,
        "license": "CC BY 4.0",
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "raw_file": str(ZIP_PATH.relative_to(PROJECT_ROOT)),
        "sha256": calculate_sha256(ZIP_PATH),
        "number_of_neighborhoods": len(neighborhoods),
        "number_of_districts": int(
            neighborhoods["district_code"].nunique()
        ),
    }

    with METADATA_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nArchivos generados:")
    print(f"  - {ZONES_CSV_PATH}")
    print(f"  - {ZONES_GEOJSON_PATH}")
    print(f"  - {METADATA_PATH}")


def main() -> None:
    create_directories()
    download_file()
    extract_zip()

    shapefile_path = find_shapefile()
    neighborhoods = build_zones_master(shapefile_path)

    validate_zones(neighborhoods)
    save_outputs(neighborhoods)

    print("\nPrimeras zonas:")
    print(
        neighborhoods.drop(columns="geometry").head(10).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()