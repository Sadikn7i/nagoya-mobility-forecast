"""
Stage 2 (pre-check) — Does month matter?

Checks whether population varies meaningfully across the 12 months of 2019,
both citywide and for a couple of specific meshes, before deciding whether
'month' is worth keeping as a model feature.

Usage:
    python check_monthly_trend.py
"""

from sqlalchemy import create_engine, text

DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

with engine.connect() as conn:
    print("=== Citywide average population by month (all meshes, daytime, all-week) ===\n")
    result = conn.execute(text("""
        SELECT month, ROUND(AVG(population)) AS avg_population
        FROM mobility_observations
        WHERE dayflag = 0 AND timezone = 1
        GROUP BY month
        ORDER BY month;
    """))
    rows = list(result)
    for row in rows:
        print(f"Month {row.month:>2}: {row.avg_population:,.0f}")

    values = [r.avg_population for r in rows]
    spread = max(values) - min(values)
    pct_spread = spread / min(values) * 100
    print(f"\nRange: {min(values):,.0f} - {max(values):,.0f}  (spread: {pct_spread:.1f}%)")

    print("\n=== Same check, but just for the busiest mesh (Nagoya Station, 52366700) ===\n")
    result = conn.execute(text("""
        SELECT month, ROUND(AVG(population)) AS avg_population
        FROM mobility_observations
        WHERE mesh1kmid = 52366700 AND dayflag = 0 AND timezone = 1
        GROUP BY month
        ORDER BY month;
    """))
    rows = list(result)
    for row in rows:
        print(f"Month {row.month:>2}: {row.avg_population:,.0f}")

    values = [r.avg_population for r in rows]
    spread = max(values) - min(values)
    pct_spread = spread / min(values) * 100
    print(f"\nRange: {min(values):,.0f} - {max(values):,.0f}  (spread: {pct_spread:.1f}%)")

    print("\n=== Same check, for a quiet peripheral mesh (Minato ward area) ===\n")
    result = conn.execute(text("""
        SELECT mo.month, ROUND(AVG(mo.population)) AS avg_population
        FROM mobility_observations mo
        JOIN mesh_areas ma ON mo.mesh1kmid = ma.mesh1kmid
        WHERE ma.cityname = '名古屋市港区' AND mo.dayflag = 0 AND mo.timezone = 1
        GROUP BY mo.month
        ORDER BY mo.month;
    """))
    rows = list(result)
    for row in rows:
        print(f"Month {row.month:>2}: {row.avg_population:,.0f}")

    values = [r.avg_population for r in rows]
    spread = max(values) - min(values)
    pct_spread = spread / min(values) * 100
    print(f"\nRange: {min(values):,.0f} - {max(values):,.0f}  (spread: {pct_spread:.1f}%)")