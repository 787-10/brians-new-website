#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "airportsdata",
# ]
# ///

"""Add a commercial flight to the flight log CSV.

For airports, airlines, and aircraft, you can enter a known code
(e.g. 'JFK', 'UA', 'B738') and it will auto-fill from previous entries.

New airports are automatically looked up via airportsdata and their
coordinates are added to the map in commercial.html.tera.
"""

import csv
import re
import os

import airportsdata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "static", "flights.csv")
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "templates", "commercial.html.tera")

# Load the full airportsdata database keyed by IATA code
AIRPORTS_DB = airportsdata.load("IATA")


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


def get_template_coords():
    """Parse existing airportCoords from the template."""
    with open(TEMPLATE_PATH, "r") as f:
        content = f.read()
    coords = {}
    for m in re.finditer(r'"([A-Z]{3})":\s*\[([0-9.\-]+),\s*([0-9.\-]+)\]', content):
        coords[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return coords


def add_coord_to_template(iata, lat, lng):
    """Insert a new airport coordinate into airportCoords in the template."""
    with open(TEMPLATE_PATH, "r") as f:
        content = f.read()

    # Find the last entry in airportCoords and insert after it
    # Pattern: "XYZ": [lat, lng]  (last one before the closing brace)
    pattern = r'("([A-Z]{3})":\s*\[[0-9.\-]+,\s*[0-9.\-]+\])\s*\n(\s*\};)'
    m = re.search(pattern, content)
    if m:
        indent = "    "
        new_entry = f'{m.group(1)},\n{indent}"{iata}": [{lat:.4f}, {lng:.4f}]\n{m.group(3)}'
        content = content[:m.start()] + new_entry + content[m.end():]
        with open(TEMPLATE_PATH, "w") as f:
            f.write(content)
        return True
    return False


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


def ensure_airport_coords(apt_str, existing_csv_airports, template_coords):
    """If the airport is new, look up its coordinates and add to the template."""
    m = re.search(r"\(([A-Z]{3})/", apt_str)
    if not m:
        return
    iata = m.group(1)

    if iata in template_coords:
        return

    # Look up in airportsdata
    if iata in AIRPORTS_DB:
        info = AIRPORTS_DB[iata]
        lat, lng = info["lat"], info["lon"]
        print(f"  New airport '{iata}' — found coordinates: [{lat:.4f}, {lng:.4f}]")
        if add_coord_to_template(iata, lat, lng):
            print(f"    -> Added to map in commercial.html.tera")
            template_coords[iata] = (lat, lng)
        else:
            print(f"    -> Could not auto-insert. Add manually to airportCoords:")
            print(f'       "{iata}": [{lat:.4f}, {lng:.4f}]')
    else:
        print(f"  Warning: '{iata}' not found in airportsdata.")
        lat = input(f"    Enter latitude: ").strip()
        lng = input(f"    Enter longitude: ").strip()
        if lat and lng:
            if add_coord_to_template(iata, float(lat), float(lng)):
                print(f"    -> Added to map in commercial.html.tera")
                template_coords[iata] = (float(lat), float(lng))


def main():
    rows = load_rows()
    airports, airlines, aircraft = build_lookups(rows)
    template_coords = get_template_coords()

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

    # Add coordinates for any new airports
    ensure_airport_coords(from_apt, airports, template_coords)
    ensure_airport_coords(to_apt, airports, template_coords)


if __name__ == "__main__":
    main()
