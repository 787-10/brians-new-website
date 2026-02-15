#!/usr/bin/env python3
"""Add a commercial flight to the flight log CSV.

For airports, airlines, and aircraft, you can enter a known code
(e.g. 'JFK', 'UA', 'B738') and it will auto-fill from previous entries.
"""

import csv
import re
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "flights.csv")


def load_rows():
    with open(CSV_PATH, "r", newline="") as f:
        return list(csv.reader(f))


def build_lookups(rows):
    airports = {}  # IATA -> full string  e.g. "JFK" -> "New York / John F Kennedy (JFK/KJFK)"
    airlines = {}  # 2-letter code -> full string  e.g. "UA" -> "United Airlines (UA/UAL)"
    aircraft = {}  # type code -> full string  e.g. "B738" -> "Boeing 737-800 (B738)"

    for row in rows:
        if len(row) < 10:
            continue
        for field in (row[2], row[3]):
            m = re.search(r"\(([A-Z]{3})/[A-Z]{4}\)", field)
            if m:
                airports[m.group(1)] = field
        m = re.search(r"\(([A-Z0-9]{2})/[A-Z]{3}\)", row[7])
        if m:
            airlines[m.group(1)] = row[7]
        m = re.search(r"\(([A-Z0-9]+)\)$", row[8].strip())
        if m:
            aircraft[m.group(1)] = row[8]
    return airports, airlines, aircraft


def prompt(label, lookup=None, key_label="code"):
    """Prompt for a value, optionally resolving a short code via lookup."""
    while True:
        val = input(f"  {label}: ").strip()
        if not val:
            continue

        if lookup is None:
            return val

        upper = val.upper()
        if upper in lookup:
            print(f"    -> {lookup[upper]}")
            return lookup[upper]

        if "(" in val:
            return val

        keys = sorted(lookup.keys())
        print(f"    Unknown {key_label} '{val}'.")
        if len(keys) <= 30:
            print(f"    Known: {', '.join(keys)}")
        full = input(f"    Enter full string (or Enter to keep '{val}'): ").strip()
        return full if full else val


def main():
    rows = load_rows()
    airports, airlines, aircraft = build_lookups(rows)

    print("=== Add a Flight ===")
    print("Tip: for airports/airlines/aircraft, type a code (JFK, UA, B738)")
    print("     to auto-fill from known values.\n")

    date = prompt("Date (YYYY-MM-DD)")
    flight_num = prompt("Flight number (e.g. UA1777)")
    from_apt = prompt("From airport (IATA code or full string)", airports, "airport")
    to_apt = prompt("To airport   (IATA code or full string)", airports, "airport")
    dep_time = prompt("Dep time (HH:MM:SS, or blank to skip)") or ""
    arr_time = prompt("Arr time (HH:MM:SS, or blank to skip)") or ""
    duration = prompt("Duration (HH:MM:SS, or blank to skip)") or ""
    airline = prompt("Airline  (2-letter code or full string)", airlines, "airline")
    ac_type = prompt("Aircraft (type code or full string)", aircraft, "aircraft")
    reg = input("  Registration (e.g. N12345, blank to skip): ").strip()

    new_row = [
        date, flight_num, from_apt, to_apt,
        dep_time, arr_time, duration,
        airline, ac_type, reg,
        "", "", "", "", "",   # seat number, seat type, class, reason, note
        "", "", "", "",       # dep_id, arr_id, airline_id, aircraft_id
    ]

    print("\n--- Preview ---")
    print(f"  {date}  {flight_num}  {from_apt}  ->  {to_apt}")
    print(f"  {airline}  |  {ac_type}  |  {reg}")
    confirm = input("\nAppend this flight? [Y/n] ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(new_row)

    print(f"\nAdded: {flight_num} on {date}")

    # Warn if a new airport was used that may need map coordinates
    for apt_str in (from_apt, to_apt):
        m = re.search(r"\(([A-Z]{3})/", apt_str)
        if m and m.group(1) not in airports:
            print(f"  Note: '{m.group(1)}' is a new airport — add its coordinates")
            print(f"        to airportCoords in templates/commercial.html.tera for the map.")


if __name__ == "__main__":
    main()
