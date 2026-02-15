#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "airportsdata",
# ]
# ///

"""One-time migration: convert flights CSV to JSON format."""

import csv
import json
import re
import os

import airportsdata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "static", "flights.csv")
FLIGHTS_JSON = os.path.join(SCRIPT_DIR, "static", "flights.json")
AIRPORTS_JSON = os.path.join(SCRIPT_DIR, "static", "airports.json")

AIRPORTS_DB = airportsdata.load("IATA")


def extract_iata(s):
    m = re.search(r"\(([A-Z]{3})/[A-Z]{4}\)", s)
    return m.group(1) if m else ""


def extract_city(s):
    idx = s.find(" / ")
    return s[:idx] if idx > 0 else s


def short_airport(s):
    return f"{extract_city(s)} ({extract_iata(s)})"


def extract_airline(s):
    idx = s.find(" (")
    return s[:idx] if idx > 0 else s


def trim_time(s):
    """'16:50:00' -> '16:50'"""
    return s[:5] if len(s) >= 5 else s


def main():
    with open(CSV_PATH, "r", newline="") as f:
        rows = list(csv.reader(f))

    # Skip empty rows and header
    header = None
    data_rows = []
    for row in rows:
        if not any(field.strip() for field in row):
            continue
        if header is None:
            header = row
            continue
        data_rows.append(row)

    flights = []
    iata_codes = set()

    for row in data_rows:
        if len(row) < 10:
            continue

        from_iata = extract_iata(row[2])
        to_iata = extract_iata(row[3])
        iata_codes.add(from_iata)
        iata_codes.add(to_iata)

        flights.append({
            "date": row[0],
            "flight": row[1],
            "from": short_airport(row[2]),
            "to": short_airport(row[3]),
            "fromIATA": from_iata,
            "toIATA": to_iata,
            "dep": trim_time(row[4]),
            "arr": trim_time(row[5]),
            "duration": trim_time(row[6]),
            "airline": extract_airline(row[7]),
            "aircraft": row[8],
            "reg": row[9],
        })

    # Build airport coordinates
    airports = {}
    for code in sorted(iata_codes):
        if not code:
            continue
        if code in AIRPORTS_DB:
            info = AIRPORTS_DB[code]
            airports[code] = [round(info["lat"], 4), round(info["lon"], 4)]
        else:
            print(f"Warning: no coordinates for '{code}'")

    with open(FLIGHTS_JSON, "w") as f:
        json.dump(flights, f, indent=2)
    print(f"Wrote {len(flights)} flights to {FLIGHTS_JSON}")

    with open(AIRPORTS_JSON, "w") as f:
        json.dump(airports, f, indent=2)
    print(f"Wrote {len(airports)} airports to {AIRPORTS_JSON}")


if __name__ == "__main__":
    main()
