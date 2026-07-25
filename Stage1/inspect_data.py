"""
Stage 1c — Inspect the raw MLIT people-flow CSV before building the pipeline.

Usage:
    python inspect_data.py path\to\your_file.csv
"""

import sys
import pandas as pd


def inspect(path: str):
    print(f"\n=== Loading {path} ===\n")

    df = pd.read_csv(path, nrows=5000, encoding="utf-8", low_memory=False)

    print(f"Shape (first 5000 rows only): {df.shape}")
    print(f"\nColumns:\n{list(df.columns)}")
    print(f"\nDtypes:\n{df.dtypes}")

    print("\n=== First 10 rows ===")
    print(df.head(10).to_string())

    print("\n=== Unique value counts for likely categorical columns ===")
    for col in df.columns:
        nunique = df[col].nunique()
        if nunique < 30:
            print(f"\n{col} ({nunique} unique values):")
            print(df[col].unique())

    print("\n=== Null counts ===")
    print(df.isnull().sum())

    print("\n=== Counting total rows in full file (this may take a moment) ===")
    total_rows = sum(1 for _ in open(path, encoding="utf-8")) - 1
    print(f"Total rows in file: {total_rows}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_data.py path\\to\\file.csv")
        sys.exit(1)

    inspect(sys.argv[1])