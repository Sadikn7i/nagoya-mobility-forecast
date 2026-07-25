"""
Stage 1f — Build the mesh_areas table: Nagoya mesh geometries (as PostGIS
polygons) enriched with ward names, loaded into PostgreSQL.

Usage:
    python build_mesh_areas.py
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from sqlalchemy import create_engine, text

# --- Config ---
DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

ATTRIBUTE_PATH = "data/attribute/attribute/attribute_mesh1km_2019.csv"
MASTER_PATH = "data/prefcodecitycodemaster/prefcode_citycode_master/prefcode_citycode_master_utf8_2019.csv"

NAGOYA_CITYCODES = list(range(23101, 23117))
TABLE_NAME = "mesh_areas"


def main():
    print("Loading attribute (mesh coordinates) file...")
    attr = pd.read_csv(ATTRIBUTE_PATH, encoding="utf-8", low_memory=False)
    print(f"  Total rows nationwide: {len(attr):,}")

    # Filter to Nagoya only
    nagoya_attr = attr[attr["citycode"].isin(NAGOYA_CITYCODES)].copy()
    print(f"  Rows for Nagoya: {len(nagoya_attr):,}")

    print("\nLoading prefcode/citycode master (names) file...")
    master = pd.read_csv(MASTER_PATH, encoding="utf-8", low_memory=False)
    nagoya_master = master[master["citycode"].isin(NAGOYA_CITYCODES)][["citycode", "cityname", "address"]]

    print("\nJoining ward names onto mesh data...")
    merged = nagoya_attr.merge(nagoya_master, on="citycode", how="left")
    print(f"  Merged rows: {len(merged):,}")
    print(f"  Unique wards found: {merged['cityname'].nunique()}")
    print(f"  Ward names: {sorted(merged['cityname'].unique())}")

    print("\nBuilding polygon geometries from bounding boxes...")
    merged["geometry"] = merged.apply(
        lambda row: box(row["lon_min"], row["lat_min"], row["lon_max"], row["lat_max"]),
        axis=1,
    )

    gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")

    # Keep only the columns we actually need
    gdf = gdf[["mesh1kmid", "citycode", "cityname", "address", "lon_center", "lat_center", "geometry"]]

    print("\nConnecting to PostgreSQL...")
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Make sure PostGIS extension is enabled
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

    print(f"Writing {len(gdf)} rows to table '{TABLE_NAME}'...")
    gdf.to_postgis(TABLE_NAME, engine, if_exists="replace", index=False)
    print("Done.\n")

    # Sanity check
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME};")).fetchone()[0]
        print(f"Row count in database: {count}")

        sample = conn.execute(text(f"""
            SELECT mesh1kmid, citycode, cityname, ST_AsText(geometry)
            FROM {TABLE_NAME}
            LIMIT 3;
        """)).fetchall()
        print("\nSample rows (with geometry as text):")
        for row in sample:
            print(row)


if __name__ == "__main__":
    main()