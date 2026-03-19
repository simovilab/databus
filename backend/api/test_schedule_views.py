"""
Tests for MBTA-style JSON:API endpoints.
All DB calls are mocked — uses SimpleTestCase (no PostgreSQL needed).
"""
import datetime
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from django.urls import reverse


# ---------------------------------------------------------------------------
# Fake queryset helper
# ---------------------------------------------------------------------------

class _FakeQS:
    """Minimal queryset stand-in that supports chaining + iteration."""

    def __init__(self, items):
        self._items = list(items)

    def filter(self, **kwargs):
        return self

    def __iter__(self):
        return iter(self._items)

    def values_list(self, field, flat=False):
        return [getattr(i, field, "") for i in self._items]

    def distinct(self):
        return self

    def order_by(self, *args):
        return self


def fqs(items):
    return _FakeQS(items)


# ---------------------------------------------------------------------------
# Mock model builders
# ---------------------------------------------------------------------------

def mock_route(route_id="bUCR_L1", route_type=3):
    r = MagicMock()
    r.route_id = route_id
    r.route_short_name = "L1"
    r.route_long_name = "Línea 1 UCR"
    r.route_desc = "Ruta circular UCR"
    r.route_type = route_type
    r.route_color = "0075BE"
    r.route_text_color = "FFFFFF"
    r.route_sort_order = 1
    return r


def mock_stop(stop_id="UCR_0_01"):
    s = MagicMock()
    s.stop_id = stop_id
    s.stop_name = "Parada UCR 01"
    s.stop_desc = "Frente a Ingeniería"
    s.stop_lat = 9.9365
    s.stop_lon = -84.0511
    s.location_type = 0
    s.wheelchair_boarding = 1
    return s


def mock_trip(trip_id="trip-001", route_id="bUCR_L1", direction_id=0, service_id="svc-1", shape_id="shape-001"):
    t = MagicMock()
    t.trip_id = trip_id
    t.route_id = route_id
    t.service_id = service_id
    t.direction_id = direction_id
    t.trip_headsign = "UCR Central"
    t.trip_short_name = None
    t.shape_id = shape_id
    t.wheelchair_accessible = 1
    t.bikes_allowed = 0
    return t


def mock_shape(shape_id="shape-001"):
    s = MagicMock()
    s.shape_id = shape_id
    s.shape_name = "L1 Ida"
    s.shape_from = "Terminal Norte"
    s.shape_to = "Terminal Sur"
    s.geometry.geojson = '{"type":"LineString","coordinates":[[-84.05,9.93],[-84.06,9.94]]}'
    return s


def mock_stoptime(trip_id="trip-001", stop_id="UCR_0_01", seq=1):
    st = MagicMock()
    st.trip_id = trip_id
    st.stop_id = stop_id
    st.stop_sequence = seq
    st.arrival_time = datetime.time(7, 5, 0)
    st.departure_time = datetime.time(7, 5, 0)
    st.timepoint = True
    st.pickup_type = 0
    st.drop_off_type = 0
    return st


def mock_calendar(service_id="svc-weekday"):
    c = MagicMock()
    c.service_id = service_id
    c.monday = True
    c.tuesday = True
    c.wednesday = True
    c.thursday = True
    c.friday = True
    c.saturday = False
    c.sunday = False
    c.start_date = datetime.date(2024, 1, 1)
    c.end_date = datetime.date(2024, 12, 31)
    return c


# ---------------------------------------------------------------------------
# GET /api/mbta/routes/
# ---------------------------------------------------------------------------

class RoutesViewTest(SimpleTestCase):
    @patch("api.schedule_views.Route")
    def test_returns_jsonapi_envelope(self, MockRoute):
        MockRoute.objects.filter.return_value = fqs([mock_route()])
        resp = self.client.get(reverse("schedule-routes"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.Route")
    def test_route_resource_structure(self, MockRoute):
        MockRoute.objects.filter.return_value = fqs([mock_route()])
        data = self.client.get(reverse("schedule-routes")).json()["data"]
        self.assertEqual(len(data), 1)
        r = data[0]
        self.assertEqual(r["id"], "bUCR_L1")
        self.assertEqual(r["type"], "route")
        attrs = r["attributes"]
        self.assertEqual(attrs["short_name"], "L1")
        self.assertEqual(attrs["long_name"], "Línea 1 UCR")
        self.assertEqual(attrs["type"], 3)

    @patch("api.schedule_views.Route")
    def test_filter_type_passes_through(self, MockRoute):
        MockRoute.objects.filter.return_value = fqs([mock_route(route_type=3)])
        url = reverse("schedule-routes") + "?filter[type]=3"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch("api.schedule_views.RouteStop")
    @patch("api.schedule_views.Route")
    def test_filter_stop_applies_route_stop_lookup(self, MockRoute, MockRouteStop):
        MockRouteStop.objects.filter.return_value = fqs([mock_route()])
        MockRoute.objects.filter.return_value = fqs([mock_route()])
        url = reverse("schedule-routes") + "?filter[stop]=UCR_0_01"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        MockRouteStop.objects.filter.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/mbta/stops/
# ---------------------------------------------------------------------------

class StopsViewTest(SimpleTestCase):
    @patch("api.schedule_views.Stop")
    def test_returns_jsonapi_envelope(self, MockStop):
        MockStop.objects.filter.return_value = fqs([mock_stop()])
        resp = self.client.get(reverse("schedule-stops"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.Stop")
    def test_stop_resource_structure(self, MockStop):
        MockStop.objects.filter.return_value = fqs([mock_stop()])
        data = self.client.get(reverse("schedule-stops")).json()["data"]
        s = data[0]
        self.assertEqual(s["id"], "UCR_0_01")
        self.assertEqual(s["type"], "stop")
        attrs = s["attributes"]
        self.assertEqual(attrs["name"], "Parada UCR 01")
        self.assertAlmostEqual(attrs["latitude"], 9.9365, places=4)
        self.assertAlmostEqual(attrs["longitude"], -84.0511, places=4)

    @patch("api.schedule_views.Stop")
    def test_filter_id(self, MockStop):
        MockStop.objects.filter.return_value = fqs([mock_stop("UCR_0_03")])
        url = reverse("schedule-stops") + "?filter[id]=UCR_0_03"
        data = self.client.get(url).json()["data"]
        self.assertEqual(data[0]["id"], "UCR_0_03")

    @patch("api.schedule_views.RouteStop")
    @patch("api.schedule_views.Stop")
    def test_filter_route_uses_routestop(self, MockStop, MockRouteStop):
        MockRouteStop.objects.filter.return_value = fqs([mock_stop()])
        MockStop.objects.filter.return_value = fqs([mock_stop()])
        url = reverse("schedule-stops") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        MockRouteStop.objects.filter.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/mbta/trips/
# ---------------------------------------------------------------------------

class TripsViewTest(SimpleTestCase):
    @patch("api.schedule_views.Trip")
    def test_returns_jsonapi_envelope(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        resp = self.client.get(reverse("schedule-trips"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.Trip")
    def test_trip_resource_structure(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        data = self.client.get(reverse("schedule-trips")).json()["data"]
        t = data[0]
        self.assertEqual(t["id"], "trip-001")
        self.assertEqual(t["type"], "trip")
        self.assertEqual(t["attributes"]["direction_id"], 0)
        self.assertEqual(t["attributes"]["headsign"], "UCR Central")
        self.assertEqual(t["relationships"]["route"]["data"]["id"], "bUCR_L1")
        self.assertEqual(t["relationships"]["service"]["data"]["id"], "svc-1")

    @patch("api.schedule_views.Trip")
    def test_filter_route(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip(route_id="bUCR_L1")])
        url = reverse("schedule-trips") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch("api.schedule_views.Trip")
    def test_filter_direction(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip(direction_id=1)])
        url = reverse("schedule-trips") + "?filter[direction_id]=1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# GET /api/mbta/shapes/
# ---------------------------------------------------------------------------

class ShapesViewTest(SimpleTestCase):
    @patch("api.schedule_views.GeoShape")
    def test_returns_jsonapi_envelope(self, MockShape):
        MockShape.objects.filter.return_value = fqs([mock_shape()])
        resp = self.client.get(reverse("schedule-shapes"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.GeoShape")
    def test_shape_resource_structure(self, MockShape):
        MockShape.objects.filter.return_value = fqs([mock_shape()])
        data = self.client.get(reverse("schedule-shapes")).json()["data"]
        s = data[0]
        self.assertEqual(s["id"], "shape-001")
        self.assertEqual(s["type"], "shape")
        self.assertIn("geometry", s["attributes"])
        self.assertEqual(s["attributes"]["geometry"]["type"], "LineString")

    @patch("api.schedule_views.Trip")
    @patch("api.schedule_views.GeoShape")
    def test_filter_route_uses_trip_lookup(self, MockShape, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        MockShape.objects.filter.return_value = fqs([mock_shape()])
        url = reverse("schedule-shapes") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        MockTrip.objects.filter.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/mbta/schedules/
# ---------------------------------------------------------------------------

class SchedulesViewTest(SimpleTestCase):
    def test_no_filter_returns_400(self):
        resp = self.client.get(reverse("schedule-schedules"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("errors", resp.json())

    @patch("api.schedule_views.StopTime")
    def test_filter_trip_returns_200(self, MockST):
        MockST.objects.filter.return_value = fqs([mock_stoptime()])
        url = reverse("schedule-schedules") + "?filter[trip]=trip-001"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.StopTime")
    def test_schedule_resource_structure(self, MockST):
        MockST.objects.filter.return_value = fqs([mock_stoptime()])
        url = reverse("schedule-schedules") + "?filter[trip]=trip-001"
        data = self.client.get(url).json()["data"]
        s = data[0]
        self.assertEqual(s["id"], "schedule-trip-001-1")
        self.assertEqual(s["type"], "schedule")
        self.assertEqual(s["attributes"]["stop_sequence"], 1)
        self.assertEqual(s["attributes"]["arrival_time"], "07:05:00")
        self.assertEqual(s["relationships"]["stop"]["data"]["id"], "UCR_0_01")
        self.assertEqual(s["relationships"]["trip"]["data"]["id"], "trip-001")

    @patch("api.schedule_views.StopTime")
    def test_filter_stop_returns_200(self, MockST):
        MockST.objects.filter.return_value = fqs([mock_stoptime()])
        url = reverse("schedule-schedules") + "?filter[stop]=UCR_0_01"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch("api.schedule_views.Trip")
    @patch("api.schedule_views.StopTime")
    def test_filter_route_returns_200(self, MockST, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        MockST.objects.filter.return_value = fqs([mock_stoptime()])
        url = reverse("schedule-schedules") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# GET /api/mbta/services/
# ---------------------------------------------------------------------------

class ServicesViewTest(SimpleTestCase):
    @patch("api.schedule_views.Calendar")
    def test_returns_jsonapi_envelope(self, MockCal):
        MockCal.objects.filter.return_value = fqs([mock_calendar()])
        resp = self.client.get(reverse("schedule-services"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.Calendar")
    def test_service_resource_structure(self, MockCal):
        MockCal.objects.filter.return_value = fqs([mock_calendar()])
        data = self.client.get(reverse("schedule-services")).json()["data"]
        s = data[0]
        self.assertEqual(s["id"], "svc-weekday")
        self.assertEqual(s["type"], "service")
        attrs = s["attributes"]
        self.assertEqual(attrs["start_date"], "2024-01-01")
        self.assertEqual(attrs["end_date"], "2024-12-31")
        # Mon-Fri = [0,1,2,3,4]
        self.assertEqual(attrs["valid_days"], [0, 1, 2, 3, 4])

    @patch("api.schedule_views.Calendar")
    def test_filter_id(self, MockCal):
        MockCal.objects.filter.return_value = fqs([mock_calendar("svc-weekend")])
        url = reverse("schedule-services") + "?filter[id]=svc-weekend"
        data = self.client.get(url).json()["data"]
        self.assertEqual(data[0]["id"], "svc-weekend")

    @patch("api.schedule_views.Trip")
    @patch("api.schedule_views.Calendar")
    def test_filter_route_uses_trip_lookup(self, MockCal, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        MockCal.objects.filter.return_value = fqs([mock_calendar()])
        url = reverse("schedule-services") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        MockTrip.objects.filter.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/mbta/route-patterns/
# ---------------------------------------------------------------------------

class RoutePatternsViewTest(SimpleTestCase):
    @patch("api.schedule_views.Trip")
    def test_returns_jsonapi_envelope(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        resp = self.client.get(reverse("schedule-route-patterns"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.json())

    @patch("api.schedule_views.Trip")
    def test_route_pattern_resource_structure(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip()])
        data = self.client.get(reverse("schedule-route-patterns")).json()["data"]
        p = data[0]
        self.assertEqual(p["type"], "route_pattern")
        self.assertIn("direction_id", p["attributes"])
        self.assertEqual(p["relationships"]["route"]["data"]["id"], "bUCR_L1")
        self.assertEqual(p["relationships"]["representative_trip"]["data"]["type"], "trip")

    @patch("api.schedule_views.Trip")
    def test_deduplicates_patterns(self, MockTrip):
        # Two trips with same route+direction+shape → one pattern
        t1 = mock_trip("trip-001", shape_id="shape-A")
        t2 = mock_trip("trip-002", shape_id="shape-A")  # same shape → duplicate pattern
        t3 = mock_trip("trip-003", shape_id="shape-B")  # different shape → new pattern
        MockTrip.objects.filter.return_value = fqs([t1, t2, t3])
        data = self.client.get(reverse("schedule-route-patterns")).json()["data"]
        self.assertEqual(len(data), 2)

    @patch("api.schedule_views.Trip")
    def test_filter_route(self, MockTrip):
        MockTrip.objects.filter.return_value = fqs([mock_trip(route_id="bUCR_L1")])
        url = reverse("schedule-route-patterns") + "?filter[route]=bUCR_L1"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
