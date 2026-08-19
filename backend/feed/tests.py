import io
import zipfile

from django.test import TestCase

from feed.models import Feed
from feed.schedule.exporter import build_gtfs_zip


class TestBuildGtfsZip(TestCase):
    """Minimal smoke tests for the GTFS Schedule zip exporter.

    Requires a PostGIS-enabled test database (models use PointField /
    LineStringField).  The fixture loads ~22 stops and 1117 stop_times.
    """

    fixtures = ["gtfs.json"]

    def _feed(self) -> Feed:
        feed = Feed.objects.filter(is_current=True).first()
        self.assertIsNotNone(feed, "Fixture must contain a Feed with is_current=True")
        return feed  # type: ignore[return-value]

    def test_returns_valid_zip_with_required_files(self) -> None:
        data = build_gtfs_zip(self._feed())
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        for required in ("agency.txt", "stops.txt", "stop_times.txt"):
            self.assertIn(required, names, f"{required} missing from zip")

    def test_stops_txt_header_and_row_count(self) -> None:
        data = build_gtfs_zip(self._feed())
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            text = zf.read("stops.txt").decode()
        lines = [line for line in text.splitlines() if line.strip()]
        header_cols = lines[0].split(",")
        self.assertIn("stop_id", header_cols)
        self.assertIn("stop_lat", header_cols)
        # 1 header + 22 data rows
        self.assertEqual(len(lines), 23, f"Expected 23 lines, got {len(lines)}")

    def test_stop_times_row_count(self) -> None:
        data = build_gtfs_zip(self._feed())
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            text = zf.read("stop_times.txt").decode()
        lines = [line for line in text.splitlines() if line.strip()]
        # 1 header + 1117 data rows
        self.assertEqual(len(lines), 1118, f"Expected 1118 lines, got {len(lines)}")
