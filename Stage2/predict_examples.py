"""
Stage 2c — Prediction examples.

Loads the saved Random Forest model and produces product-facing
predictions for a few named areas, matching the actual output format
described in the product spec:

    Area: Sakae
    Day type: Holiday
    Time of day: Daytime
    Predicted people: 18,400
    Historical range: 16,900-20,100

Usage:
    python predict_examples.py
"""

import joblib
import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

MODEL_PATH = "models/random_forest.joblib"

FEATURES = [
    "lon_center",
    "lat_center",
    "distance_to_station_km",
    "month",
    "dayflag",
    "timezone",
]

STATION_LON = 136.881256
STATION_LAT = 35.1708336

DAYFLAG_LABELS = {1: "Weekday", 2: "Holiday"}
TIMEZONE_LABELS = {1: "Daytime", 2: "Nighttime"}

# Named areas -> representative mesh IDs (confirmed busiest meshes per
# area from Stage 1 exploration). In a real product, the user would pick
# from a dropdown of named places; here we hardcode a few for demonstration.
NAMED_AREAS = {
    "Nagoya Station": 52366700,
    "Sakae": 52366702,
    "Naka Ward (secondary)": 52366701,
    "Higashi Ward": 52366703,
}

# Example queries to run: (area_name, month, dayflag, timezone)
EXAMPLE_QUERIES = [
    ("Sakae", 10, 2, 1),          # October, Holiday, Daytime
    ("Nagoya Station", 10, 2, 1), # October, Holiday, Daytime
    ("Nagoya Station", 10, 1, 1), # October, Weekday, Daytime (comparison)
    ("Higashi Ward", 11, 2, 2),   # November, Holiday, Nighttime
]


def haversine_km(lon1, lat1, lon2, lat2):
    import numpy as np
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def main():
    print("Loading model and mesh coordinates...")
    model = joblib.load(MODEL_PATH)

    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    with engine.connect() as conn:
        mesh_coords = pd.read_sql(
            text("SELECT mesh1kmid, cityname, lon_center, lat_center FROM mesh_areas"),
            conn,
        )
        historical = pd.read_sql(
            text("""
                SELECT mesh1kmid, month, dayflag, timezone, population
                FROM mobility_observations
                WHERE dayflag != 0 AND timezone != 0
            """),
            conn,
        )

    mesh_coords = mesh_coords.set_index("mesh1kmid")

    print("\n" + "=" * 60)
    print("PREDICTION EXAMPLES")
    print("=" * 60)

    for area_name, month, dayflag, timezone in EXAMPLE_QUERIES:
        mesh_id = NAMED_AREAS[area_name]
        coords = mesh_coords.loc[mesh_id]
        dist = haversine_km(coords["lon_center"], coords["lat_center"], STATION_LON, STATION_LAT)

        X = pd.DataFrame([{
            "lon_center": coords["lon_center"],
            "lat_center": coords["lat_center"],
            "distance_to_station_km": dist,
            "month": month,
            "dayflag": dayflag,
            "timezone": timezone,
        }])[FEATURES]

        predicted = model.predict(X)[0]

        # Historical range: same mesh, same dayflag/timezone, across all
        # 12 months of 2019 (this is the honest "expected range" — the
        # actual observed spread for this exact condition).
        hist = historical[
            (historical["mesh1kmid"] == mesh_id)
            & (historical["dayflag"] == dayflag)
            & (historical["timezone"] == timezone)
        ]
        hist_min = hist["population"].min()
        hist_max = hist["population"].max()
        hist_avg = hist["population"].mean()

        print(f"\nArea: {area_name} ({coords['cityname']})")
        print(f"Month: {month}   Day type: {DAYFLAG_LABELS[dayflag]}   Time: {TIMEZONE_LABELS[timezone]}")
        print(f"Predicted people: {predicted:,.0f}")
        print(f"Historical range (2019, same day/time type): {hist_min:,.0f} - {hist_max:,.0f}")
        print(f"Historical average: {hist_avg:,.0f}")
        diff_pct = (predicted - hist_avg) / hist_avg * 100
        print(f"vs historical average: {diff_pct:+.1f}%")


if __name__ == "__main__":
    main()