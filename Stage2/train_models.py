"""
Stage 2b — Train/test split (by month) + Baseline + Random Forest + XGBoost.
Saves all results to disk: metrics, feature importances, predictions,
and the trained models themselves.

Split: train on Jan-Sep 2019, test on Oct-Dec 2019.

Usage:
    python train_models.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

DATA_PATH = "data/nagoya_2019_features.parquet"
RESULTS_DIR = Path("results")
MODELS_DIR = Path("models")

FEATURES = [
    "lon_center",
    "lat_center",
    "distance_to_station_km",
    "month",
    "dayflag",
    "timezone",
]
TARGET = "population"


def evaluate(name, y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"\n--- {name} ---")
    print(f"MAE:  {mae:,.0f}")
    print(f"RMSE: {rmse:,.0f}")
    print(f"R2:   {r2:.4f}")
    return {"model": name, "mae": mae, "rmse": rmse, "r2": r2}


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    MODELS_DIR.mkdir(exist_ok=True)

    print("Loading feature table...")
    df = pd.read_parquet(DATA_PATH)
    print(f"Total rows: {len(df):,}")

    train = df[df["month"] <= 9].copy()
    test = df[df["month"] >= 10].copy()
    print(f"Train rows (Jan-Sep): {len(train):,}")
    print(f"Test rows (Oct-Dec):  {len(test):,}")

    X_train, y_train = train[FEATURES], train[TARGET]
    X_test, y_test = test[FEATURES], test[TARGET]

    metrics_results = []
    importance_rows = []
    predictions = test[["mesh1kmid", "month", "dayflag", "timezone", "population"]].copy()

    # --- Baseline ---
    print("\n=== Baseline: mesh's historical average (Jan-Sep) ===")
    mesh_avg = train.groupby("mesh1kmid")[TARGET].mean()
    baseline_preds = test["mesh1kmid"].map(mesh_avg).fillna(train[TARGET].mean())
    metrics_results.append(evaluate("Baseline (mesh average)", y_test, baseline_preds))
    predictions["pred_baseline"] = baseline_preds.values

    # --- Random Forest ---
    print("\n=== Random Forest ===")
    rf = RandomForestRegressor(n_estimators=300, max_depth=12, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    metrics_results.append(evaluate("Random Forest", y_test, rf_preds))
    predictions["pred_random_forest"] = rf_preds

    for feat, imp in zip(FEATURES, rf.feature_importances_):
        importance_rows.append({"model": "Random Forest", "feature": feat, "importance": imp})

    joblib.dump(rf, MODELS_DIR / "random_forest.joblib")

    # --- XGBoost ---
    print("\n=== XGBoost ===")
    xgb_model = xgb.XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05, random_state=42
    )
    xgb_model.fit(X_train, y_train)
    xgb_preds = xgb_model.predict(X_test)
    metrics_results.append(evaluate("XGBoost", y_test, xgb_preds))
    predictions["pred_xgboost"] = xgb_preds

    for feat, imp in zip(FEATURES, xgb_model.feature_importances_):
        importance_rows.append({"model": "XGBoost", "feature": feat, "importance": imp})

    xgb_model.save_model(MODELS_DIR / "xgboost.json")

    # --- Save everything to disk ---
    print("\n" + "=" * 50)
    print("Saving results to disk...")
    print("=" * 50)

    metrics_df = pd.DataFrame(metrics_results)
    metrics_path = RESULTS_DIR / "stage2_model_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"Saved: {metrics_path}")

    importance_df = pd.DataFrame(importance_rows)
    importance_path = RESULTS_DIR / "stage2_feature_importances.csv"
    importance_df.to_csv(importance_path, index=False)
    print(f"Saved: {importance_path}")

    predictions_path = RESULTS_DIR / "stage2_test_predictions.csv"
    predictions.to_csv(predictions_path, index=False)
    print(f"Saved: {predictions_path}")

    # Also save a small run-summary JSON (useful for the README/docs later)
    summary = {
        "train_rows": len(train),
        "test_rows": len(test),
        "features_used": FEATURES,
        "target": TARGET,
        "split": "month <= 9 train, month >= 10 test",
        "metrics": metrics_results,
    }
    summary_path = RESULTS_DIR / "stage2_run_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved: {summary_path}")

    print(f"\nModels saved to: {MODELS_DIR}/random_forest.joblib and {MODELS_DIR}/xgboost.json")

    # --- Final printed summary ---
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for r in metrics_results:
        print(f"{r['model']:<28} MAE={r['mae']:>8,.0f}  RMSE={r['rmse']:>8,.0f}  R2={r['r2']:.4f}")


if __name__ == "__main__":
    main()