"""
Stage 1e — Load all 12 months of 2019 Aichi data, filter to Nagoya,
and save as one clean parquet file.

Usage:
    python build_nagoya_2019.py
"""

import pandas as pd
from pathlib import Path

# --- Config ---
BASE_DIR = Path("data/monthly_mdp_mesh1km_23/23/2019")
OUTPUT_PATH = Path("data/nagoya_2019_clean.parquet")

# Nagoya's 16 wards = citycode 23101 through 23116
NAGOYA_CITYCODES = list(range(23101, 23117))

MONTHS = [f"{i:02d}" for i in range(1, 13)]  # "01".."12"


def load_month(month: str) -> pd.DataFrame:
    file_path = BASE_DIR / month / "monthly_mdp_mesh1km.csv"
    if not file_path.exists():
        print(f"  WARNING: missing file for month {month}: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path, encoding="utf-8", low_memory=False)
    return df


def main():
    all_months = []

    print("Loading all 12 months of 2019...\n")
    for month in MONTHS:
        print(f"  Loading month {month}...")
        df = load_month(month)
        if df.empty:
            continue
        all_months.append(df)

    print(f"\nLoaded {len(all_months)} months. Concatenating...")
    full_df = pd.concat(all_months, ignore_index=True)
    print(f"Total rows (all Aichi, all months): {len(full_df):,}")

    # Filter to Nagoya wards only
    nagoya_df = full_df[full_df["citycode"].isin(NAGOYA_CITYCODES)].copy()
    print(f"Total rows (Nagoya only): {len(nagoya_df):,}")

    # Basic sanity checks
    print("\n=== Sanity checks ===")
    print(f"Unique citycodes in filtered data: {sorted(nagoya_df['citycode'].unique())}")
    print(f"Unique mesh IDs: {nagoya_df['mesh1kmid'].nunique()}")
    print(f"Months present: {sorted(nagoya_df['month'].unique())}")
    print(f"Null counts:\n{nagoya_df.isnull().sum()}")

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    nagoya_df.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved cleaned Nagoya 2019 data to: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()