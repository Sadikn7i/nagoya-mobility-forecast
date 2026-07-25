"""
Stage 2a — Feature engineering.

Pulls mobility_observations + mesh_areas from PostgreSQL, joins them,
adds a distance-to-city-center feature, and saves an ML-ready table.

Usage:
    python build_features.py
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

OUTPUT_PATH = "data/nagoya_2019_features.parquet"

# Nagoya Station mesh (52366700) center coordinates, confirmed as the
# busiest mesh in Stage 1 — used as the reference point for a
# distance-to-center feature.
STATION_LON = 136.881256
STATION_LAT = 35.1708336


def haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in km between two lon/lat points."""
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def main():
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    print("Pulling joined data from PostgreSQL...")
    query = text("""
        SELECT
            mo.mesh1kmid,
            mo.year,
            mo.month,
            mo.dayflag,
            mo.timezone,
            mo.population,
            ma.cityname,
            ma.lon_center,
            ma.lat_center
        FROM mobility_observations mo
        JOIN mesh_areas ma ON mo.mesh1kmid = ma.mesh1kmid
        WHERE mo.dayflag != 0 AND mo.timezone != 0
    """)
    # Note: we drop dayflag=0 (All day) and timezone=0 (All day) rows here,
    # since those are aggregates OF the weekday/holiday and day/night rows,
    # not independent observations. Keeping them would let the model
    # "cheat" by learning near-duplicate rows.

    df = pd.read_sql(query, engine)
    print(f"Rows pulled: {len(df):,}")

    print("\nEngineering features...")

    # Distance to Nagoya Station (the confirmed busiest mesh / city center)
    df["distance_to_station_km"] = haversine_km(
        df["lon_center"], df["lat_center"], STATION_LON, STATION_LAT
    )

    # Human-readable labels kept for reference, but model will use the
    # underlying numeric codes (dayflag, timezone) directly.
    df["dayflag_label"] = df["dayflag"].map({1: "weekday", 2: "holiday"})
    df["timezone_label"] = df["timezone"].map({1: "daytime", 2: "nighttime"})

    print(df[["mesh1kmid", "month", "dayflag_label", "timezone_label",
              "distance_to_station_km", "population"]].head(10).to_string())

    print("\nFeature summary:")
    print(df[["lon_center", "lat_center", "distance_to_station_km", "population"]].describe())

    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved feature table to: {OUTPUT_PATH}")
    print(f"Final shape: {df.shape}")


if __name__ == "__main__":
    main()