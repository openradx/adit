#!/usr/bin/env python3
"""Convert a CSV file of mass transfer filters into JSON compatible with
the MassTransferJob.filters_json form field.

CSV columns (all optional, header names must match):
    study_description, series_description, modality, institution_name

Usage examples:
    python scripts/csv_to_mass_transfer_filters.py filters.csv
    python scripts/csv_to_mass_transfer_filters.py filters.csv --delimiter ";"
    python scripts/csv_to_mass_transfer_filters.py filters.csv --min-age 18
    python scripts/csv_to_mass_transfer_filters.py filters.csv --min-age 18 --max-age 90
    python scripts/csv_to_mass_transfer_filters.py filters.csv --min-series-instances 5
    python scripts/csv_to_mass_transfer_filters.py filters.csv -o output.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

KNOWN_COLUMNS = {"study_description", "series_description", "modality", "institution_name"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a CSV of mass transfer filters to JSON.",
    )
    parser.add_argument("csv_file", type=Path, help="Path to the input CSV file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=None,
        help="Set a constant min_age for every filter",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=None,
        help="Set a constant max_age for every filter",
    )
    parser.add_argument(
        "--min-series-instances",
        type=int,
        default=None,
        help="Set a constant min_number_of_series_related_instances for every filter",
    )
    parser.add_argument(
        "-d",
        "--delimiter",
        default=",",
        help="CSV column delimiter (default: ',')",
    )
    return parser.parse_args(argv)


def csv_to_filters(
    csv_path: Path,
    *,
    delimiter: str = ",",
    min_age: int | None = None,
    max_age: int | None = None,
    min_number_of_series_related_instances: int | None = None,
) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise SystemExit(f"Error: {csv_path} appears to be empty or has no header row.")

        normalised_headers = {h.strip().lower(): h for h in reader.fieldnames}
        unknown = set(normalised_headers) - KNOWN_COLUMNS - {""}
        if unknown:
            print(
                f"Warning: ignoring unknown columns: {', '.join(sorted(unknown))}",
                file=sys.stderr,
            )

        filters: list[dict] = []
        for row_num, row in enumerate(reader, start=2):
            entry: dict = {}
            for col in KNOWN_COLUMNS:
                original_header = normalised_headers.get(col)
                if original_header is not None:
                    value = row[original_header].strip()
                    if value:
                        entry[col] = value

            if min_age is not None:
                entry["min_age"] = min_age
            if max_age is not None:
                entry["max_age"] = max_age
            if min_number_of_series_related_instances is not None:
                entry["min_number_of_series_related_instances"] = (
                    min_number_of_series_related_instances
                )

            if not entry:
                print(f"Warning: skipping empty row {row_num}", file=sys.stderr)
                continue

            filters.append(entry)

    return filters


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if not args.csv_file.exists():
        raise SystemExit(f"Error: file not found: {args.csv_file}")

    if args.min_age is not None and args.min_age < 0:
        raise SystemExit("Error: --min-age must be non-negative")
    if args.max_age is not None and args.max_age < 0:
        raise SystemExit("Error: --max-age must be non-negative")
    if (
        args.min_age is not None
        and args.max_age is not None
        and args.min_age > args.max_age
    ):
        raise SystemExit(
            f"Error: --min-age ({args.min_age}) cannot exceed --max-age ({args.max_age})"
        )
    if args.min_series_instances is not None and args.min_series_instances < 1:
        raise SystemExit("Error: --min-series-instances must be at least 1")

    filters = csv_to_filters(
        args.csv_file,
        delimiter=args.delimiter,
        min_age=args.min_age,
        max_age=args.max_age,
        min_number_of_series_related_instances=args.min_series_instances,
    )

    if not filters:
        raise SystemExit("Error: no valid filter rows found in CSV.")

    output = json.dumps(filters, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {len(filters)} filter(s) to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
