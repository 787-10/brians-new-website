from datetime import timedelta
import unittest
from unittest.mock import mock_open, patch

import add_flight
from add_flight import calculate_flight_duration, extract_iata, format_duration


class CalculateFlightDurationTests(unittest.TestCase):
    def test_uses_airport_offsets_for_the_departure_date(self):
        self.assertEqual(
            calculate_flight_duration(
                "2026-01-15", "PHX", "JFK", "10:00", "16:00"
            ),
            timedelta(hours=4),
        )
        self.assertEqual(
            calculate_flight_duration(
                "2026-07-15", "PHX", "JFK", "10:00", "16:00"
            ),
            timedelta(hours=3),
        )

    def test_infers_international_arrival_date_from_elapsed_time(self):
        self.assertEqual(
            calculate_flight_duration(
                "2026-07-15", "LAX", "HND", "12:00", "15:00"
            ),
            timedelta(hours=11),
        )
        self.assertEqual(
            calculate_flight_duration(
                "2026-07-15", "HND", "LAX", "17:00", "10:00"
            ),
            timedelta(hours=9),
        )
        self.assertEqual(
            calculate_flight_duration(
                "2026-07-15", "CXI", "HNL", "14:00", "20:00"
            ),
            timedelta(hours=6),
        )

    def test_formats_duration_for_the_flight_log(self):
        self.assertEqual(
            format_duration(timedelta(hours=11, minutes=5)),
            "11:05",
        )

    def test_rejects_ambiguous_and_nonexistent_dst_wall_times(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            calculate_flight_duration(
                "2026-11-01", "JFK", "LAX", "01:30", "08:00"
            )
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_flight_duration(
                "2026-03-08", "JFK", "LAX", "02:30", "08:00"
            )

    def test_accepts_a_bare_iata_code(self):
        self.assertEqual(extract_iata("sfo"), "SFO")


class AddFlightCliTests(unittest.TestCase):
    @patch("add_flight.json.dump")
    @patch("add_flight.open", new_callable=mock_open)
    @patch("add_flight.load_airports")
    @patch("add_flight.load_flights")
    def test_main_saves_the_calculated_duration(
        self, load_flights, load_airports, _open, dump
    ):
        load_flights.return_value = [
            {
                "fromIATA": "PHX",
                "from": "Phoenix (PHX)",
                "toIATA": "JFK",
                "to": "New York (JFK)",
                "airline": "United Airlines",
                "aircraft": "Boeing 737-800 (B738)",
            }
        ]
        load_airports.return_value = {"PHX": [0, 0], "JFK": [0, 0]}
        answers = iter(
            [
                "2026-07-15",
                "UA1",
                "PHX",
                "JFK",
                "10:00",
                "16:00",
                "United Airlines (UA)",
                "B738",
                "",
                "",
            ]
        )

        with patch("builtins.input", side_effect=answers):
            add_flight.main()

        saved_flights = dump.call_args_list[0].args[0]
        self.assertEqual(saved_flights[-1]["duration"], "03:00")


if __name__ == "__main__":
    unittest.main()
