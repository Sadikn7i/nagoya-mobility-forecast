"""
Stage 1g — Sanity check: run a real spatial JOIN connecting
mobility_observations (population) with mesh_areas (geometry + ward names).

Usage:
    python query_check.py
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
    print("=== Average population by ward (all-day, all-week average) ===\n")
    result = conn.execute(text("""
        SELECT
            ma.cityname,
            ROUND(AVG(mo.population)) AS avg_population
        FROM mobility_observations mo
        JOIN mesh_areas ma ON mo.mesh1kmid = ma.mesh1kmid
        WHERE mo.dayflag = 0 AND mo.timezone = 0
        GROUP BY ma.cityname
        ORDER BY avg_population DESC;
    """))
    for row in result:
        print(f"{row.cityname}: {row.avg_population:,.0f}")

    print("\n=== Busiest single mesh, with its ward name and coordinates ===\n")
    result = conn.execute(text("""
        SELECT
            mo.mesh1kmid,
            ma.cityname,
            ma.lon_center,
            ma.lat_center,
            ROUND(AVG(mo.population)) AS avg_population
        FROM mobility_observations mo
        JOIN mesh_areas ma ON mo.mesh1kmid = ma.mesh1kmid
        GROUP BY mo.mesh1kmid, ma.cityname, ma.lon_center, ma.lat_center
        ORDER BY avg_population DESC
        LIMIT 5;
    """))
    for row in result:
        print(row)

    print("\n=== Weekday vs Holiday comparison (daytime only) ===\n")
    result = conn.execute(text("""
        SELECT
            ma.cityname,
            mo.dayflag,
            ROUND(AVG(mo.population)) AS avg_population
        FROM mobility_observations mo
        JOIN mesh_areas ma ON mo.mesh1kmid = ma.mesh1kmid
        WHERE mo.timezone = 1 AND mo.dayflag IN (1, 2)
        GROUP BY ma.cityname, mo.dayflag
        ORDER BY ma.cityname, mo.dayflag;
    """))
    for row in result:
        day_label = "Weekday" if row.dayflag == 1 else "Holiday"
        print(f"{row.cityname} ({day_label}): {row.avg_population:,.0f}")