"""Tests for the GTFS Schedule zip importer.

Requires a PostGIS-enabled test database (models use PointField). HTTP is
mocked at the module boundary (`feed.schedule.importer.requests`) since
there's no `responses`/`requests-mock` dependency in this project.
"""

import io
import zipfile
from unittest.mock import Mock, patch

from django.test import TestCase

from feed.models import (
    Agency,
    Calendar,
    CalendarDate,
    Feed,
    GTFSProvider,
    Route,
    Shape,
    Stop,
    StopTime,
    Trip,
)
from feed.schedule.importer import import_schedule_if_changed
from schedule_engine.tasks import fetch_schedule


def _build_gtfs_zip_bytes(*, lean_stop_times: bool = False) -> bytes:
    """Build a tiny but complete in-memory GTFS zip covering all imported tables.

    With ``lean_stop_times=True``, stop_times.txt mirrors the real bUCR feed's
    columns exactly (no pickup_type/drop_off_type at all) -- the shape that
    exposed the "column absent entirely" NOT NULL bug.
    """
    stop_times_txt = (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,timepoint,"
        "shape_dist_traveled,stop_headsign\n"
        "T1,08:00:00,08:00:00,S1,1,1,0.0,\n"
        "T1,08:10:00,08:10:00,S2,2,1,1.2,\n"
        if lean_stop_times
        else (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type\n"
            "T1,08:00:00,08:00:00,S1,1,,\n"
            "T1,08:10:00,08:10:00,S2,2,,\n"
        )
    )
    files = {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "A1,Test Agency,https://example.com,America/Costa_Rica\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
            "S1,Stop One,9.930000,-84.080000,\n"
            "S2,Stop Two,9.935000,-84.085000,\n"
        ),
        "shapes.txt": (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
            "SH1,9.930000,-84.080000,1\n"
            "SH1,9.935000,-84.085000,2\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
            "start_date,end_date\n"
            "WD,1,1,1,1,1,0,0,20260101,20261231\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\nWD,20260101,2\n"
        ),
        "routes.txt": (
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            "R1,A1,1,Route One,3\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,direction_id,wheelchair_accessible,bikes_allowed\n"
            "R1,WD,T1,0,,\n"
        ),
        "stop_times.txt": stop_times_txt,
        "feed_info.txt": (
            "feed_publisher_name,feed_publisher_url,feed_lang\n"
            "Test Publisher,https://example.com,es\n"
        ),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _mock_head_response(etag: str | None = '"abc123"', last_modified: str | None = None) -> Mock:
    headers = {}
    if etag is not None:
        headers["ETag"] = etag
    if last_modified is not None:
        headers["Last-Modified"] = last_modified
    resp = Mock()
    resp.headers = headers
    resp.raise_for_status = Mock()
    return resp


def _mock_get_response(content: bytes) -> Mock:
    resp = Mock()
    resp.content = content
    resp.raise_for_status = Mock()
    return resp


class TestImportScheduleIfChanged(TestCase):
    """Cover new-import, unchanged, and missing-header cases for import_schedule_if_changed."""

    def _provider(self, **kwargs: object) -> GTFSProvider:
        defaults: dict[str, object] = {
            "code": "TESTP",
            "name": "Test Provider",
            "schedule_url": "https://example.com/gtfs.zip",
            "timezone": "America/Costa_Rica",
            "is_active": True,
        }
        defaults.update(kwargs)
        return GTFSProvider.objects.create(**defaults)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_new_etag_imports_and_populates_tables(
        self, mock_head: Mock, mock_get: Mock
    ) -> None:
        provider = self._provider()
        mock_head.return_value = _mock_head_response(etag='"new-etag"')
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes())

        result = import_schedule_if_changed(provider)

        self.assertTrue(result)
        feeds = Feed.objects.filter(gtfs_provider=provider, is_current=True)
        self.assertEqual(feeds.count(), 1)
        feed = feeds.first()
        self.assertEqual(feed.http_etag, '"new-etag"')

        self.assertEqual(Route.objects.filter(feed=feed).count(), 1)
        self.assertEqual(Trip.objects.filter(feed=feed).count(), 1)
        self.assertEqual(Stop.objects.filter(feed=feed).count(), 2)
        self.assertEqual(StopTime.objects.filter(feed=feed).count(), 2)
        self.assertEqual(Shape.objects.filter(feed=feed).count(), 2)
        self.assertEqual(Calendar.objects.filter(feed=feed).count(), 1)
        self.assertEqual(CalendarDate.objects.filter(feed=feed).count(), 1)

        stop = Stop.objects.filter(feed=feed).first()
        self.assertIsNotNone(stop.stop_point)
        # parent_station is a non-nullable CharField with a blank cell in the
        # CSV; it must be coerced to "" (not None) or bulk_create would raise
        # a NotNullViolation.
        self.assertEqual(stop.parent_station, "")

        trip = Trip.objects.filter(feed=feed).first()
        self.assertIsNone(trip.linked_route)
        # blank direction_id/wheelchair_accessible/bikes_allowed -> coerced to 0
        self.assertEqual(trip.direction_id, 0)
        self.assertEqual(trip.wheelchair_accessible, 0)
        self.assertEqual(trip.bikes_allowed, 0)

        stop_time = StopTime.objects.filter(feed=feed, stop_id="S1").first()
        self.assertEqual(stop_time.pickup_type, 0)
        self.assertEqual(stop_time.drop_off_type, 0)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_lean_stop_times_missing_pickup_drop_off_columns_imports_as_zero(
        self, mock_head: Mock, mock_get: Mock
    ) -> None:
        """Real bUCR feed shape: stop_times.txt has no pickup_type/drop_off_type

        columns at all (not just blank cells). Those StopTime fields are
        non-nullable with no default, so an entirely-absent column must still
        be coerced to 0, not left as None.
        """
        provider = self._provider()
        mock_head.return_value = _mock_head_response(etag='"lean-etag"')
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes(lean_stop_times=True))

        result = import_schedule_if_changed(provider)

        self.assertTrue(result)
        feed = Feed.objects.filter(gtfs_provider=provider, is_current=True).first()
        self.assertIsNotNone(feed)
        stop_times = StopTime.objects.filter(feed=feed)
        self.assertEqual(stop_times.count(), 2)
        for stop_time in stop_times:
            self.assertEqual(stop_time.pickup_type, 0)
            self.assertEqual(stop_time.drop_off_type, 0)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_same_etag_skips_import(self, mock_head: Mock, mock_get: Mock) -> None:
        provider = self._provider()
        current_feed = Feed.objects.create(
            feed_id="TESTP (existing)",
            gtfs_provider=provider,
            http_etag='"same-etag"',
            is_current=True,
        )
        mock_head.return_value = _mock_head_response(etag='"same-etag"')

        result = import_schedule_if_changed(provider)

        self.assertFalse(result)
        mock_get.assert_not_called()
        self.assertEqual(Feed.objects.count(), 1)
        current_feed.refresh_from_db()
        self.assertTrue(current_feed.is_current)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_changed_etag_flips_previous_current_feed(
        self, mock_head: Mock, mock_get: Mock
    ) -> None:
        provider = self._provider()
        old_feed = Feed.objects.create(
            feed_id="TESTP (old)",
            gtfs_provider=provider,
            http_etag='"old-etag"',
            is_current=True,
        )
        mock_head.return_value = _mock_head_response(etag='"new-etag"')
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes())

        result = import_schedule_if_changed(provider)

        self.assertTrue(result)
        old_feed.refresh_from_db()
        self.assertFalse(old_feed.is_current)
        self.assertEqual(Feed.objects.filter(is_current=True).count(), 1)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_missing_etag_header_falls_back_and_still_imports(
        self, mock_head: Mock, mock_get: Mock
    ) -> None:
        provider = self._provider()
        Feed.objects.create(
            feed_id="TESTP (existing)",
            gtfs_provider=provider,
            http_etag=None,
            is_current=True,
        )
        # No ETag, no Last-Modified -> can't prove unchanged -> proceed with import.
        mock_head.return_value = _mock_head_response(etag=None, last_modified=None)
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes())

        result = import_schedule_if_changed(provider)

        self.assertTrue(result)
        self.assertEqual(Feed.objects.filter(is_current=True).count(), 1)

    def test_no_schedule_url_returns_false(self) -> None:
        provider = self._provider(schedule_url="")
        result = import_schedule_if_changed(provider)
        self.assertFalse(result)
        self.assertEqual(Feed.objects.count(), 0)

    @patch("feed.models.StopTime.objects.bulk_create")
    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_mid_import_failure_rolls_back_whole_feed(
        self, mock_head: Mock, mock_get: Mock, mock_bulk_create: Mock
    ) -> None:
        """A failure partway through (here, stop_times) must leave no trace: no new
        Feed, and none of the earlier tables' rows (agency, stops, ...) persisted.
        """
        provider = self._provider()
        mock_head.return_value = _mock_head_response(etag='"new-etag"')
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes())
        mock_bulk_create.side_effect = RuntimeError("simulated mid-import DB failure")

        result = import_schedule_if_changed(provider)

        self.assertFalse(result)
        self.assertEqual(Feed.objects.count(), 0)
        self.assertEqual(Agency.objects.count(), 0)
        self.assertEqual(Stop.objects.count(), 0)
        self.assertEqual(Route.objects.count(), 0)
        self.assertEqual(Trip.objects.count(), 0)


class TestFetchScheduleTask(TestCase):
    """Cover the fetch_schedule Celery task's provider iteration."""

    def test_no_active_providers_returns_message(self) -> None:
        GTFSProvider.objects.create(
            code="INACTIVE",
            name="Inactive Provider",
            schedule_url="https://example.com/gtfs.zip",
            timezone="America/Costa_Rica",
            is_active=False,
        )
        result = fetch_schedule()
        self.assertIn("no active providers", result)
        self.assertEqual(Feed.objects.count(), 0)

    @patch("feed.schedule.importer.requests.get")
    @patch("feed.schedule.importer.requests.head")
    def test_active_provider_gets_updated(self, mock_head: Mock, mock_get: Mock) -> None:
        provider = GTFSProvider.objects.create(
            code="ACTIVEP",
            name="Active Provider",
            schedule_url="https://example.com/gtfs.zip",
            timezone="America/Costa_Rica",
            is_active=True,
        )
        mock_head.return_value = _mock_head_response(etag='"etag-1"')
        mock_get.return_value = _mock_get_response(_build_gtfs_zip_bytes())

        result = fetch_schedule()

        self.assertIn("ACTIVEP", result)
        self.assertIn("updated=", result)
        self.assertEqual(
            Feed.objects.filter(gtfs_provider=provider, is_current=True).count(), 1
        )
