"""
Stage 2 — Load cleaned Nagoya 2019 data into PostgreSQL.

Creates a `mobility_observations` table and loads the parquet file into it.

Usage:
    python load_to_postgres.py
"""

import pandas as pd
from sqlalchemy import create_engine, text

# --- Config ---
DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

PARQUET_PATH = "data/nagoya_2019_clean.parquet"
TABLE_NAME = "mobility_observations"


def main():
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Test connection
    print("Connecting to PostgreSQL...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print(f"Connected. {result.fetchone()[0]}\n")

    # Load the parquet file
    print(f"Loading {PARQUET_PATH}...")
    df = pd.read_parquet(PARQUET_PATH)
    print(f"Loaded {len(df):,} rows.\n")

    # Write to Postgres (replaces table if it already exists)
    print(f"Writing to table '{TABLE_NAME}'...")
    df.to_sql(TABLE_NAME, engine, if_exists="replace", index=False, chunksize=5000)
    print("Done.\n")

    # Sanity check: query it back
    with engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME};")).fetchone()[0]
        print(f"Row count in database: {count:,}")

        sample = conn.execute(text(f"SELECT * FROM {TABLE_NAME} LIMIT 5;")).fetchall()
        print("\nSample rows:")
        for row in sample:
            print(row)

        avg_by_mesh = conn.execute(text(f"""
            SELECT mesh1kmid, AVG(population) as avg_population
            FROM {TABLE_NAME}
            GROUP BY mesh1kmid
            ORDER BY avg_population DESC
            LIMIT 5;
        """)).fetchall()
        print("\nTop 5 busiest meshes (by average population):")
        for row in avg_by_mesh:
            print(row)


if __name__ == "__main__":
    main()