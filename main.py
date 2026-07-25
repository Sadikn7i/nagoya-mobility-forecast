"""
Stage 3 — FastAPI service wrapping the Nagoya mobility model + database.

Endpoints:
    GET /areas                     - list all Nagoya meshes/wards
    GET /flow/{area_id}            - historical population data for a mesh
    GET /prediction/{area_id}      - predicted population for a mesh under given conditions

Usage:
    uvicorn main:app --reload
Then open:
    http://127.0.0.1:8000/docs     - interactive API docs (auto-generated)
"""

from datetime import datetime
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

# --- Config ---
DB_USER = "postgres"
DB_PASSWORD = "nagoya123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "peopleflow"

MODEL_PATH = "models/random_forest.joblib"

STATION_LON = 136.881256
STATION_LAT = 35.1708336

FEATURES = ["lon_center", "lat_center", "distance_to_station_km", "month", "dayflag", "timezone"]

DAYFLAG_LABELS = {1: "Weekday", 2: "Holiday"}
TIMEZONE_LABELS = {1: "Daytime", 2: "Nighttime"}

# --- App setup ---
app = FastAPI(
    title="Nagoya Mobility Forecast API",
    description="Predicts stay-population for Nagoya mesh areas based on real MLIT people-flow data (2019).",
    version="1.0.0",
)

# Allow the React dev server (Vite default: localhost:5173) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
model = joblib.load(MODEL_PATH)


def haversine_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def get_mesh_or_404(mesh_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM mesh_areas WHERE mesh1kmid = :mesh_id"),
            {"mesh_id": mesh_id},
        ).mappings().first()
    if result is None:
        raise HTTPException(status_code=404, detail=f"Area '{mesh_id}' not found")
    return result


@app.get("/")
def root():
    return {
        "message": "Nagoya Mobility Forecast API",
        "endpoints": ["/areas", "/flow/{area_id}", "/prediction/{area_id}"],
        "docs": "/docs",
    }


@app.get("/areas")
def list_areas():
    """List all Nagoya mesh areas with their ward name and coordinates."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT mesh1kmid, cityname, lon_center, lat_center
            FROM mesh_areas
            ORDER BY cityname, mesh1kmid;
        """)).mappings().all()

    return {
        "count": len(rows),
        "areas": [
            {
                "area_id": row["mesh1kmid"],
                "ward": row["cityname"],
                "lon": row["lon_center"],
                "lat": row["lat_center"],
            }
            for row in rows
        ],
    }


@app.get("/flow/{area_id}")
def get_flow(area_id: int):
    """Historical population data for a given mesh, across all of 2019."""
    mesh = get_mesh_or_404(area_id)

    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT month, dayflag, timezone, population
                FROM mobility_observations
                WHERE mesh1kmid = :mesh_id AND dayflag != 0 AND timezone != 0
                ORDER BY month, dayflag, timezone;
            """),
            {"mesh_id": area_id},
        ).mappings().all()

    return {
        "area_id": area_id,
        "ward": mesh["cityname"],
        "history": [
            {
                "month": row["month"],
                "day_type": DAYFLAG_LABELS[row["dayflag"]],
                "time_of_day": TIMEZONE_LABELS[row["timezone"]],
                "population": row["population"],
            }
            for row in rows
        ],
    }


@app.get("/prediction/{area_id}")
def predict(
    area_id: int,
    month: int = Query(default=datetime.now().month, ge=1, le=12, description="Month (1-12)"),
    dayflag: int = Query(default=2, ge=1, le=2, description="1=Weekday, 2=Holiday"),
    timezone: int = Query(default=1, ge=1, le=2, description="1=Daytime, 2=Nighttime"),
):
    """Predicted population for a mesh under the given month/day-type/time-of-day."""
    mesh = get_mesh_or_404(area_id)

    dist = haversine_km(mesh["lon_center"], mesh["lat_center"], STATION_LON, STATION_LAT)

    X = pd.DataFrame([{
        "lon_center": mesh["lon_center"],
        "lat_center": mesh["lat_center"],
        "distance_to_station_km": dist,
        "month": month,
        "dayflag": dayflag,
        "timezone": timezone,
    }])[FEATURES]

    predicted = float(model.predict(X)[0])

    with engine.connect() as conn:
        hist = conn.execute(
            text("""
                SELECT population FROM mobility_observations
                WHERE mesh1kmid = :mesh_id AND dayflag = :dayflag AND timezone = :timezone
            """),
            {"mesh_id": area_id, "dayflag": dayflag, "timezone": timezone},
        ).scalars().all()

    hist_min = min(hist) if hist else None
    hist_max = max(hist) if hist else None
    hist_avg = sum(hist) / len(hist) if hist else None

    return {
        "area_id": area_id,
        "ward": mesh["cityname"],
        "month": month,
        "day_type": DAYFLAG_LABELS[dayflag],
        "time_of_day": TIMEZONE_LABELS[timezone],
        "predicted_people": round(predicted),
        "historical_range": {"min": hist_min, "max": hist_max} if hist else None,
        "historical_average": round(hist_avg) if hist_avg else None,
        "vs_historical_average_pct": (
            round((predicted - hist_avg) / hist_avg * 100, 1) if hist_avg else None
        ),
    }