# Nagoya Mobility Forecast

A mini people-flow prediction system built on real Japanese
mobile-location data. Predicts stay-population across 325 mesh areas
in Nagoya City, based on real MLIT (Ministry of Land, Infrastructure,
Transport and Tourism) open data from 2019.

> Given an area, month, day-type (weekday/holiday), and time-of-day
> (daytime/nighttime), predict the expected stay population — with an
> honest historical range, not a fabricated confidence interval.

Built as a complete, working pipeline: real data → cleaned and stored
in a spatial database → trained ML model → live API → interactive
console — not a notebook demo.

---

## What this actually does

A user selects a mesh area on the map of Nagoya and a time condition
(month / weekday-or-holiday / day-or-night). The system returns:

- A predicted stay-population figure
- The real historical range observed for that exact condition across
  all of 2019 (not a statistically invented confidence interval)
- How the prediction compares to that mesh's yearly average

This mirrors a real operational question a city planner, retailer, or
transit company might ask: *"how busy will this area likely be, given
what we know about how it normally behaves?"*

---

## Architecture

```
MLIT CSV/ZIP data (2019, Aichi Prefecture, 1km mesh)
        |
        v
Python + Pandas   ->  clean, filter to Nagoya's 16 wards
        |
        v
PostgreSQL + PostGIS  ->  mobility_observations, mesh_areas (real polygon geometry)
        |
        v
SQL spatial analysis   ->  heatmap queries, seasonal trend checks
        |
        v
Python + scikit-learn   ->  feature engineering, Random Forest / XGBoost
        |
        v
FastAPI    ->  GET /areas, GET /flow/{id}, GET /prediction/{id}
        |
        v
React + Leaflet    ->  live interactive console
```

---

## Results

- **Data:** 35,065 real observations across 325 meshes, 12 months of
  2019 (pre-COVID, deliberately excluding 2020-2021)
- **Model:** Random Forest, MAE 582 people, R² 0.987 on a genuine
  Oct-Dec holdout (roughly halves the error of a historical-average
  baseline)
- **Key finding:** distance to Nagoya Station is the dominant
  predictor (60% feature importance) — day-of-week and month barely
  matter on their own, but month becomes a real signal specifically at
  high-traffic central meshes (up to 38% seasonal swing at Nagoya
  Station vs. ~6% citywide)

Full methodology and honest discussion of tradeoffs in each stage doc
below.

---

## Stack

| Layer | Technology |
|---|---|
| Data source | MLIT nationwide people-flow open data (G空間情報センター) |
| Processing | Python, pandas, geopandas, pyarrow |
| Database | PostgreSQL + PostGIS (via Docker) |
| Machine learning | scikit-learn (Random Forest), XGBoost |
| API | FastAPI, SQLAlchemy, joblib |
| Frontend | React (Vite), react-leaflet, hand-built SVG charts |
| Environment | Docker, VS Code, Git |

---

## Project structure

```
Flow_Prediction_System/
  data/                        raw + cleaned data (not committed - see .gitignore)
  models/                      trained model files (random_forest.joblib, xgboost.json)
  results/                     Stage 2 metrics, predictions, feature importances
  docs/                        stage-by-stage documentation (this is the real writeup)
    STAGE1_DATA_PIPELINE.md
    STAGE2_ANALYTICS_ML.md
    STAGE3_API.md
    STAGE4_FRONTEND.md
  frontend/                    React + Vite app
  main.py                      FastAPI application
  build_nagoya_2019.py         Stage 1: clean + consolidate raw CSVs
  load_to_postgres.py          Stage 1: load into PostgreSQL
  build_mesh_areas.py          Stage 1: build PostGIS geometry table
  build_features.py            Stage 2: feature engineering
  train_models.py              Stage 2: train + evaluate models
  predict_examples.py          Stage 2: product-facing prediction examples
```

---

## Running it locally

**Prerequisites:** Python 3.12+, Node.js 18+, Docker Desktop

**1. Database**
```powershell
docker run --name nagoya-db -e POSTGRES_PASSWORD=nagoya123 -e POSTGRES_DB=peopleflow -p 5432:5432 -d postgis/postgis:16-3.4
```

**2. Backend**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install pandas geopandas pyarrow psycopg2-binary sqlalchemy scikit-learn xgboost fastapi "uvicorn[standard]" geoalchemy2 joblib
uvicorn main:app --reload
```
API docs available at `http://127.0.0.1:8000/docs`

**3. Frontend** (separate terminal)
```powershell
cd frontend
npm install
npm run dev
```
Console available at `http://localhost:5173`

*(Full step-by-step, including where to download the source data, is
in `docs/STAGE1_DATA_PIPELINE.md`.)*

---

## Documentation

Each stage is documented in full, including real decisions made, real
bugs hit, and how they were diagnosed and fixed:

- [`docs/STAGE1_DATA_PIPELINE.md`](docs/STAGE1_DATA_PIPELINE.md) — data acquisition, cleaning, PostGIS setup
- [`docs/STAGE2_ANALYTICS_ML.md`](docs/STAGE2_ANALYTICS_ML.md) — feature engineering, model training and evaluation
- [`docs/STAGE3_API.md`](docs/STAGE3_API.md) — FastAPI service design and endpoints
- [`docs/STAGE4_FRONTEND.md`](docs/STAGE4_FRONTEND.md) — React console, design decisions, real debugging log

---

## Known limitations

Documented honestly rather than glossed over:

- **Time resolution is monthly, not hourly.** The MLIT dataset records
  monthly averages broken into weekday/holiday and daytime/nighttime
  buckets — not per-hour data. The product is framed accordingly
  ("Holiday, Daytime" rather than "Saturday 2pm").
- **2019 only.** 2020-2021 data exists in the same dataset but was
  excluded deliberately, since COVID-era mobility patterns would
  distort what the model learns as "normal."
- **No authentication or rate limiting** on the API — fine for a local
  portfolio project, would need addressing before any public deployment.
- **Single-year training data** means the model has seen one full
  seasonal cycle. More years of data (were they available without
  COVID distortion) would likely improve the model's grasp of genuine
  seasonality vs. one-year noise.

---

## Data attribution

Built on the Ministry of Land, Infrastructure, Transport and Tourism's
nationwide people-flow open data, hosted on G空間情報センター
(geospatial.jp). Stay-population figures are converted population
estimates calculated by Agoop Co., Ltd. from mobile device location
data. Released as part of a survey on COVID-19 countermeasures;
covers January 2019 - December 2021.