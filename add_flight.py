#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "airportsdata",
# ]
# ///

"""Add a commercial flight to the flight log.

For airports, airlines, and aircraft, you can enter a known code
(e.g. 'JFK', 'UA', 'B738') and it will auto-fill from previous entries.

New airports are automatically looked up via airportsdata and their
coordinates are added to airports.json for the map.
"""

import json
import re
import os
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import airportsdata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FLIGHTS_JSON = os.path.join(SCRIPT_DIR, "static", "flights.json")
AIRPORTS_JSON = os.path.join(SCRIPT_DIR, "static", "airports.json")

# Load the full airportsdata database keyed by IATA code
AIRPORTS_DB = airportsdata.load("IATA")
MAX_INFERRED_DURATION = timedelta(hours=24)


def _localize_wall_time(local_date, wall_time, zone, label):
    """Attach a zone only when a local wall time maps to one real instant."""
    naive = datetime.combine(local_date, wall_time)
    candidates = []
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(timezone.utc).astimezone(zone)
        if (
            round_trip.replace(tzinfo=None) == naive
            and round_trip.fold == fold
        ):
            candidates.append(candidate)

    if not candidates:
        raise ValueError(f"{label} local time does not exist due to DST")
    if len(candidates) > 1:
        raise ValueError(f"{label} local time is ambiguous due to DST")
    return candidates[0]


def calculate_flight_duration(date, from_iata, to_iata, dep_time, arr_time):
    """Return elapsed time for a flight lasting no more than 24 hours."""
    try:
        flight_date = date_type.fromisoformat(date)
        departure_time = time.fromisoformat(dep_time)
        arrival_time = time.fromisoformat(arr_time)
    except ValueError as error:
        raise ValueError(f"Invalid flight date or time: {error}") from error

    def airport_zone(iata):
        airport = AIRPORTS_DB.get(iata.upper())
        if not airport or not airport.get("tz"):
            raise ValueError(f"No timezone data for airport '{iata}'")
        return ZoneInfo(airport["tz"])

    origin_zone = airport_zone(from_iata)
    destination_zone = airport_zone(to_iata)

    departure = _localize_wall_time(
        flight_date, departure_time, origin_zone, "Departure"
    )
    departure_utc = departure.astimezone(timezone.utc)
    elapsed_candidates = []
    for day_offset in (-1, 0, 1, 2):
        arrival_date = flight_date + timedelta(days=day_offset)
        arrival = datetime.combine(
            arrival_date, arrival_time, destination_zone
        )
        elapsed = arrival.astimezone(timezone.utc) - departure_utc
        if timedelta(0) < elapsed <= MAX_INFERRED_DURATION:
            elapsed_candidates.append((elapsed, arrival_date))

    if not elapsed_candidates:
        raise ValueError(
            "Could not infer an arrival date for a flight within 24 hours"
        )

    _, inferred_arrival_date = min(elapsed_candidates)
    arrival = _localize_wall_time(
        inferred_arrival_date, arrival_time, destination_zone, "Arrival"
    )
    return arrival.astimezone(timezone.utc) - departure_utc


def format_duration(duration):
    """Format a timedelta as the HH:MM value stored in flights.json."""
    total_minutes = int(duration.total_seconds()) // 60
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def load_flights():
    with open(FLIGHTS_JSON, "r") as f:
        return json.load(f)


def load_airports():
    with open(AIRPORTS_JSON, "r") as f:
        return json.load(f)


def build_lookups(flights):
    airports = {}  # IATA -> display string  e.g. "JFK" -> "New York (JFK)"
    airlines = {}  # uppercase name -> saved display name
    aircraft = {}  # type code -> full string  e.g. "B744" -> "Boeing 747-400 (B744)"

    for f in flights:
        # Airports: extract IATA from "from"/"to" fields or use fromIATA/toIATA
        airports[f["fromIATA"]] = f["from"]
        airports[f["toIATA"]] = f["to"]

        # Airlines: normalize names to match prompt()'s case-insensitive lookup
        airlines[f["airline"].upper()] = f["airline"]

        # Aircraft: extract code from parenthesized suffix
        m = re.search(r"\(([A-Z0-9]+)\)$", f["aircraft"].strip())
        if m:
            aircraft[m.group(1)] = f["aircraft"]

    return airports, airlines, aircraft


def extract_iata(display_str):
    """Extract IATA code from a display string like 'New York (JFK)'."""
    m = re.search(r"\(([A-Z]{3})\)", display_str)
    if m:
        return m.group(1)
    bare_code = display_str.strip().upper()
    return bare_code if re.fullmatch(r"[A-Z]{3}", bare_code) else ""


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


def trim_time(s):
    """'16:50:00' -> '16:50'"""
    return s[:5] if len(s) >= 5 else s


def ensure_airport_coords(iata, airport_coords):
    """If the airport is new, look up its coordinates and add to airports.json."""
    if not iata or iata in airport_coords:
        return

    if iata in AIRPORTS_DB:
        info = AIRPORTS_DB[iata]
        lat, lng = round(info["lat"], 4), round(info["lon"], 4)
        print(f"  New airport '{iata}' — found coordinates: [{lat}, {lng}]")
        airport_coords[iata] = [lat, lng]
        print(f"    -> Will be saved to airports.json")
    else:
        print(f"  Warning: '{iata}' not found in airportsdata.")
        lat = input(f"    Enter latitude: ").strip()
        lng = input(f"    Enter longitude: ").strip()
        if lat and lng:
            airport_coords[iata] = [round(float(lat), 4), round(float(lng), 4)]
            print(f"    -> Will be saved to airports.json")


def main():
    flights = load_flights()
    airport_coords = load_airports()
    airports, airlines, aircraft = build_lookups(flights)

    print("=== Add a Flight ===")
    print("Tip: for airports/aircraft, type a code (JFK, B738)")
    print("     to auto-fill from known values.\n")

    date = prompt("Date (YYYY-MM-DD)")
    flight_num = prompt("Flight number (e.g. UA1777)")
    from_apt = prompt("From airport (IATA code or full string)", airports, "airport")
    to_apt = prompt("To airport   (IATA code or full string)", airports, "airport")
    dep_time = trim_time(prompt("Dep time (HH:MM, or blank to skip)") or "")
    arr_time = trim_time(prompt("Arr time (HH:MM, or blank to skip)") or "")

    from_iata = extract_iata(from_apt)
    to_iata = extract_iata(to_apt)
    try:
        duration = format_duration(
            calculate_flight_duration(
                date, from_iata, to_iata, dep_time, arr_time
            )
        )
        print(f"  Duration: {duration} (calculated)")
    except (ValueError, ZoneInfoNotFoundError) as error:
        print(f"  Could not calculate duration: {error}")
        duration = trim_time(prompt("Duration (HH:MM)") or "")

    airline = prompt("Airline  (name or known value)", airlines, "airline")
    ac_type = prompt("Aircraft (type code or full string)", aircraft, "aircraft")
    reg = input("  Registration (e.g. N12345, blank to skip): ").strip()

    new_flight = {
        "date": date,
        "flight": flight_num,
        "from": from_apt,
        "to": to_apt,
        "fromIATA": from_iata,
        "toIATA": to_iata,
        "dep": dep_time,
        "arr": arr_time,
        "duration": duration,
        "airline": airline,
        "aircraft": ac_type,
        "reg": reg,
    }

    print("\n--- Preview ---")
    print(f"  {date}  {flight_num}  {from_apt}  ->  {to_apt}")
    print(f"  {airline}  |  {ac_type}  |  {reg}")
    confirm = input("\nAppend this flight? [Y/n] ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return

    # Append to flights list (newest at end; template reverses for display)
    flights.append(new_flight)

    with open(FLIGHTS_JSON, "w") as f:
        json.dump(flights, f, indent=2)
    print(f"\nAdded: {flight_num} on {date}")

    # Add coordinates for any new airports
    coords_changed = False
    for iata in (from_iata, to_iata):
        old_len = len(airport_coords)
        ensure_airport_coords(iata, airport_coords)
        if len(airport_coords) > old_len:
            coords_changed = True

    if coords_changed:
        # Write sorted by IATA code
        sorted_coords = dict(sorted(airport_coords.items()))
        with open(AIRPORTS_JSON, "w") as f:
            json.dump(sorted_coords, f, indent=2)
        print("  airports.json updated.")


if __name__ == "__main__":
    main()
