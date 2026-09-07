"""Smoke tests for the GTFS Schedule zip exporter.

The feed under test is built imperatively in `setUpTestData` rather than
loaded from a fixture bundle: the schedule now comes from the upstream
importer (`manage.py bootstrap_schedule` / the hourly `fetch_schedule` task),
so there is no checked-in GTFS dump to load, and building only the rows these
assertions need keeps the expected counts visible in the test itself.

Requires a PostGIS-enabled test database (models use PointField /
LineStringField).
"""

import io
import zipfile

from django.contrib.gis.geos import Point
from django.test import TestCase

from feed.models import Feed as FeedModel

from feed.models import Agency, Calendar, Feed, Route, Stop, StopTime, Trip

STOP_COUNT = 3
STOP_TIMES_PER_TRIP = STOP_COUNT
TRIP_COUNT = 2
STOP_TIME_COUNT = TRIP_COUNT * STOP_TIMES_PER_TRIP


class TestBuildGtfsZip(TestCase):
    """Verify the exporter emits a well-formed zip with every row it was given."""

    feed: FeedModel

    @classmethod
    def setUpTestData(cls) -> None:
        """Build one current Feed with an agency, a route, 3 stops and 2 trips."""
        cls.feed = Feed.objects.create(feed_id="test-feed", is_current=True)

        Agency.objects.create(
            feed=cls.feed,
            agency_id="SIMOVI",
            agency_name="SIMOVI",
            agency_url="https://simovi.org/",
            agency_timezone="America/Costa_Rica",
        )
        Calendar.objects.create(
            feed=cls.feed,
            service_id="weekday",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        Route.objects.create(
            feed=cls.feed,
            route_id="route-1",
            agency_id="SIMOVI",
            route_short_name="1",
            route_long_name="Test Route",
            route_type=3,
        )

        for index in range(STOP_COUNT):
            lat, lon = 9.9 + index * 0.01, -84.1 + index * 0.01
            Stop.objects.create(
                feed=cls.feed,
                stop_id=f"stop-{index}",
                stop_name=f"Stop {index}",
                stop_lat=lat,
                stop_lon=lon,
                stop_point=Point(lon, lat),
            )

        for trip_index in range(TRIP_COUNT):
            trip_id = f"trip-{trip_index}"
            Trip.objects.create(
                feed=cls.feed,
                trip_id=trip_id,
                route_id="route-1",
                service_id="weekday",
                direction_id=trip_index,
                # Non-nullable in the gtfs-django base model; 0 is GTFS's
                # "no information available".
                wheelchair_accessible=0,
                bikes_allowed=0,
            )
            for seq in range(STOP_TIMES_PER_TRIP):
                StopTime.objects.create(
                    feed=cls.feed,
                    trip_id=trip_id,
                    stop_id=f"stop-{seq}",
                    stop_sequence=seq,
                    arrival_time=f"0{6 + trip_index}:{seq * 10:02d}:00",
                    departure_time=f"0{6 + trip_index}:{seq * 10:02d}:00",
                    # Non-nullable in the gtfs-django base model; 0 is GTFS's
                    # "regularly scheduled pickup/drop off".
                    pickup_type=0,
                    drop_off_type=0,
                )

    def _zip_lines(self, name: str) -> list[str]:
        """Export the feed and return the non-blank lines of `name` inside the zip."""
        from feed.schedule.exporter import build_gtfs_zip

        data = build_gtfs_zip(self.feed)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            text = zf.read(name).decode()
        return [line for line in text.splitlines() if line.strip()]

    def test_returns_valid_zip_with_required_files(self) -> None:
        """The export is a non-empty zip containing the required GTFS files."""
        from feed.schedule.exporter import build_gtfs_zip

        data = build_gtfs_zip(self.feed)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        for required in ("agency.txt", "stops.txt", "stop_times.txt"):
            self.assertIn(required, names, f"{required} missing from zip")

    def test_stops_txt_header_and_row_count(self) -> None:
        """stops.txt carries the GTFS columns and one row per stop."""
        lines = self._zip_lines("stops.txt")
        header_cols = lines[0].split(",")
        self.assertIn("stop_id", header_cols)
        self.assertIn("stop_lat", header_cols)
        # The internal stop_point/stop_heading columns are not GTFS.
        self.assertNotIn("stop_point", header_cols)
        self.assertEqual(len(lines), STOP_COUNT + 1)

    def test_stop_times_row_count(self) -> None:
        """stop_times.txt has one row per (trip, stop) pair."""
        lines = self._zip_lines("stop_times.txt")
        self.assertEqual(len(lines), STOP_TIME_COUNT + 1)
