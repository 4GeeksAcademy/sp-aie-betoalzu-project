#!/usr/bin/env python3
"""Nexova support ticket analyzer.

Usage:
    python analyze.py incidents-nexova.csv
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api.analyzer import analyze_csv, export_metrics, print_report


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python analyze.py <incidents.csv>")
        return 1

    file_path = Path(argv[1])
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: file not found: {file_path}")
        return 1

    result = analyze_csv(file_path)
    print_report(result)

    try:
        answer = input("Export results to CSV? [y / n]: ").strip().lower()
    except EOFError:
        return 0

    if answer == "y":
        output_file = file_path.with_name(f"{file_path.stem}-metrics.csv")
        export_metrics(result, output_file)
        print(f"Metrics exported to: {output_file.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))