from unittest.mock import patch, MagicMock
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.contrib.auth.models import User


# ---------------------------------------------------------------------------
# Helpers for realtime tests
# ---------------------------------------------------------------------------

SAMPLE_REDIS_STATE = {
    "runs:in_progress": {"run:001"},
    "run:001": {
        "vehicle": "unit-10",
        "trip_id": "trip-bUCR_L1-0700",
        "route_id": "bUCR_L1",
        "direction_id": "0",
        "start_time": "07:00:00",
        "start_date": "2024-01-15",
        "schedule_relationship": "SCHEDULED",
    },
    "vehicle:unit-10:data": {
        "id": "unit-10",
        "label": "Bus 10",
        "license_plate": "ABC-123",
    },
    "vehicle:unit-10:position": {
        "latitude": "9.9365",
        "longitude": "-84.0511",
        "speed": "14.0",
        "bearing": "270.0",
        "timestamp": "1705337502",
    },
    "vehicle:unit-10:progression": {
        "current_stop_sequence": "5",
        "stop_id": "UCR_0_05",
        "current_status": "IN_TRANSIT_TO",
        "congestion_level": "RUNNING_SMOOTHLY",
    },
    "vehicle:unit-10:occupancy": {
        "occupancy_status": "FEW_SEATS_AVAILABLE",
        "occupancy_percentage": "40",
    },
}

SAMPLE_TRIP_UPDATES = {
    "header": {"gtfs_realtime_version": "2.0", "timestamp": 1705337502},
    "entity": [
        {
            "id": "unit-10",
            "trip_update": {
                "timestamp": 1705337502,
                "trip": {
                    "trip_id": "trip-bUCR_L1-0700",
                    "route_id": "bUCR_L1",
                    "direction_id": 0,
                    "start_time": "07:00:00",
                    "start_date": "20240115",
                    "schedule_relationship": "SCHEDULED",
                },
                "vehicle": {"id": "unit-10", "label": "Bus 10"},
                "stop_time_update": [
                    {
                        "stop_sequence": 5,
                        "stop_id": "UCR_0_05",
                        "arrival": {"time": 1705337850, "uncertainty": 120},
                        "departure": {"time": 1705337910, "uncertainty": 120},
                    },
                    {
                        "stop_sequence": 6,
                        "stop_id": "UCR_0_06",
                        "arrival": {"time": 1705338030, "uncertainty": 120},
                        "departure": {"time": 1705338090, "uncertainty": 120},
                    },
                ],
            },
        }
    ],
}


def make_redis_mock():
    """Return a mock Redis client pre-seeded with SAMPLE_REDIS_STATE."""
    mock_r = MagicMock()
    mock_r.smembers.side_effect = lambda key: SAMPLE_REDIS_STATE.get(key, set())
    mock_r.hgetall.side_effect = lambda key: SAMPLE_REDIS_STATE.get(key, {})
    return mock_r


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class LoginViewTest(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "testpassword"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )
        self.url = reverse("login")

    def test_login_success(self):
        response = self.client.post(
            self.url, {"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_login_failure(self):
        response = self.client.post(
            self.url, {"username": self.username, "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


# ---------------------------------------------------------------------------
# GET /api/realtime/vehicles/
# ---------------------------------------------------------------------------


class RealtimeVehiclesViewTest(SimpleTestCase):
    def _mock_redis(self):
        patcher = patch("api.realtime_views._get_redis", return_value=make_redis_mock())
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_returns_all_vehicles_when_no_filter(self):
        self._mock_redis()
        response = self.client.get(reverse("realtime-vehicles"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "unit-10")
        self.assertEqual(data[0]["type"], "vehicle")

    def test_vehicle_attributes_are_correct(self):
        self._mock_redis()
        response = self.client.get(reverse("realtime-vehicles"))
        attrs = response.json()["data"][0]["attributes"]
        self.assertAlmostEqual(attrs["latitude"], 9.9365, places=4)
        self.assertAlmostEqual(attrs["longitude"], -84.0511, places=4)
        self.assertAlmostEqual(attrs["speed"], 14.0, places=1)
        self.assertEqual(attrs["current_status"], "IN_TRANSIT_TO")
        self.assertEqual(attrs["current_stop_sequence"], 5)
        self.assertEqual(attrs["stop_id"], "UCR_0_05")
        self.assertEqual(attrs["occupancy_status"], "FEW_SEATS_AVAILABLE")
        self.assertEqual(attrs["occupancy_percentage"], 40)

    def test_vehicle_relationships_are_correct(self):
        self._mock_redis()
        response = self.client.get(reverse("realtime-vehicles"))
        rels = response.json()["data"][0]["relationships"]
        self.assertEqual(rels["trip"]["data"]["id"], "trip-bUCR_L1-0700")
        self.assertEqual(rels["route"]["data"]["id"], "bUCR_L1")
        self.assertEqual(rels["stop"]["data"]["id"], "UCR_0_05")

    def test_filter_by_route_returns_match(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[route]=bUCR_L1"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)

    def test_filter_by_route_returns_empty_for_no_match(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[route]=bUCR_L2"
        response = self.client.get(url)
        self.assertEqual(len(response.json()["data"]), 0)

    def test_filter_by_trip_returns_match(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[trip]=trip-bUCR_L1-0700"
        response = self.client.get(url)
        self.assertEqual(len(response.json()["data"]), 1)

    def test_filter_by_trip_returns_empty_for_no_match(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[trip]=nonexistent-trip"
        response = self.client.get(url)
        self.assertEqual(len(response.json()["data"]), 0)

    def test_filter_by_vehicle_id(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[vehicle]=unit-10"
        response = self.client.get(url)
        self.assertEqual(len(response.json()["data"]), 1)

    def test_filter_by_vehicle_id_no_match(self):
        self._mock_redis()
        url = reverse("realtime-vehicles") + "?filter[vehicle]=unit-99"
        response = self.client.get(url)
        self.assertEqual(len(response.json()["data"]), 0)

    def test_empty_redis_returns_empty_list(self):
        empty_mock = MagicMock()
        empty_mock.smembers.return_value = set()
        with patch("api.realtime_views._get_redis", return_value=empty_mock):
            response = self.client.get(reverse("realtime-vehicles"))
        self.assertEqual(response.json()["data"], [])


# ---------------------------------------------------------------------------
# GET /api/realtime/predictions/
# ---------------------------------------------------------------------------


class RealtimePredictionsViewTest(SimpleTestCase):
    def _mock_feed(self):
        patcher = patch(
            "api.realtime_views._load_trip_updates",
            return_value=SAMPLE_TRIP_UPDATES,
        )
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_filter_by_trip_returns_predictions(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[trip]=trip-bUCR_L1-0700"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["type"], "prediction")

    def test_prediction_attributes_are_correct(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[trip]=trip-bUCR_L1-0700"
        data = self.client.get(url).json()["data"]
        first = data[0]
        self.assertEqual(first["attributes"]["stop_sequence"], 5)
        self.assertEqual(first["attributes"]["stop_id"], "UCR_0_05")
        self.assertEqual(first["attributes"]["uncertainty"], 120)
        self.assertEqual(first["attributes"]["schedule_relationship"], "SCHEDULED")
        self.assertIsNotNone(first["attributes"]["arrival_time"])
        self.assertIsNotNone(first["attributes"]["departure_time"])

    def test_prediction_relationships_are_correct(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[trip]=trip-bUCR_L1-0700"
        data = self.client.get(url).json()["data"]
        rels = data[0]["relationships"]
        self.assertEqual(rels["stop"]["data"]["id"], "UCR_0_05")
        self.assertEqual(rels["trip"]["data"]["id"], "trip-bUCR_L1-0700")
        self.assertEqual(rels["route"]["data"]["id"], "bUCR_L1")
        self.assertEqual(rels["vehicle"]["data"]["id"], "unit-10")

    def test_filter_by_stop_returns_matching_predictions(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[stop]=UCR_0_05"
        response = self.client.get(url)
        data = response.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["attributes"]["stop_id"], "UCR_0_05")

    def test_filter_by_stop_no_match_returns_empty(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[stop]=UCR_9_99"
        data = self.client.get(url).json()["data"]
        self.assertEqual(data, [])

    def test_filter_by_trip_no_match_returns_empty(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[trip]=nonexistent"
        data = self.client.get(url).json()["data"]
        self.assertEqual(data, [])

    def test_no_filter_returns_all_predictions(self):
        self._mock_feed()
        response = self.client.get(reverse("realtime-predictions"))
        data = response.json()["data"]
        self.assertEqual(len(data), 2)

    def test_include_stop_adds_included_array(self):
        self._mock_feed()
        mock_stop = MagicMock()
        mock_stop.stop_id = "UCR_0_05"
        mock_stop.stop_name = "Parada UCR 05"
        mock_stop.stop_lat = 9.9366
        mock_stop.stop_lon = -84.0512

        mock_qs = MagicMock()
        mock_qs.values.return_value = [
            {
                "stop_id": "UCR_0_05",
                "stop_name": "Parada UCR 05",
                "stop_lat": 9.9366,
                "stop_lon": -84.0512,
            }
        ]
        with patch("api.realtime_views.Stop") as MockStop:
            MockStop.objects.filter.return_value = mock_qs
            url = (
                reverse("realtime-predictions")
                + "?filter[trip]=trip-bUCR_L1-0700&include=stop"
            )
            response = self.client.get(url)

        body = response.json()
        self.assertIn("included", body)
        self.assertEqual(len(body["included"]), 1)
        inc = body["included"][0]
        self.assertEqual(inc["type"], "stop")
        self.assertEqual(inc["id"], "UCR_0_05")
        self.assertEqual(inc["attributes"]["name"], "Parada UCR 05")

    def test_include_stop_not_present_without_param(self):
        self._mock_feed()
        url = reverse("realtime-predictions") + "?filter[trip]=trip-bUCR_L1-0700"
        body = self.client.get(url).json()
        self.assertNotIn("included", body)

    def test_feed_unavailable_returns_503(self):
        with patch(
            "api.realtime_views._load_trip_updates",
            side_effect=FileNotFoundError,
        ):
            response = self.client.get(reverse("realtime-predictions"))
        self.assertEqual(response.status_code, 503)
