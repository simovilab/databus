from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from feed.models import Feed, Trip
from realtime_engine.tasks import validate_run
from schedule_engine.models import Operator, Run, Vehicle

# ---------------------------------------------------------------------------
# Base valid payload — all cases start from this and mutate one field
# ---------------------------------------------------------------------------
def valid_run():
    return {
        "vehicle_id": "v-test",
        "operator_id": "op-test",
        "route_id": "r-test",
        "trip_id": "t-test",
        "direction_id": 0,
        "shape_id": "s-test",
        "start_date": date.today().strftime("%Y-%m-%d"),
        "start_time": "07:15:00",
        "schedule_relationship": "SCHEDULED",
    }


def run(data):
    """Call validate_run synchronously (no Celery broker needed)."""
    return validate_run.apply(args=[data]).get()


def show(case_num, description, data, result, expected):
    status = "PASS" if result == expected else "FAIL"
    print(f"\n[{status}] Case {case_num}: {description}")
    print(f"       Input  : {data}")
    print(f"       Result : {result}  (expected {expected})")


class ValidateRunTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.vehicle = Vehicle.objects.create(id="v-test", license_plate="TST-001")

        user = User.objects.create_user(username="op_test", password="pw")
        cls.operator = Operator.objects.create(id="op-test", user=user)

        cls.feed = Feed.objects.create(feed_id="feed-test", is_current=True)

        # bulk_create skips the overridden save() that requires Route + Calendar to exist
        Trip.objects.bulk_create([
            Trip(
                feed=cls.feed,
                trip_id="t-test",
                route_id="r-test",
                service_id="svc-test",
                direction_id=0,
                shape_id="s-test",
                wheelchair_accessible=0,
                bikes_allowed=0,
            )
        ])

    # ------------------------------------------------------------------
    # Case 1 — Happy path
    # ------------------------------------------------------------------
    def test_case_01_valid(self):
        data = valid_run()
        result = run(data)
        show(1, "All fields correct", data, result, True)
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # Case 2 — Required field completely absent
    # ------------------------------------------------------------------
    def test_case_02_missing_vehicle_id(self):
        data = valid_run()
        del data["vehicle_id"]
        result = run(data)
        show(2, "vehicle_id key missing from payload", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 3 — Required field present but empty string
    # ------------------------------------------------------------------
    def test_case_03_empty_trip_id(self):
        data = valid_run()
        data["trip_id"] = ""
        result = run(data)
        show(3, "trip_id is empty string", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 4 — direction_id cannot be cast to int
    # ------------------------------------------------------------------
    def test_case_04_invalid_direction_id(self):
        data = valid_run()
        data["direction_id"] = "norte"
        result = run(data)
        show(4, "direction_id is non-numeric string 'norte'", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 5 — start_date has wrong format
    # ------------------------------------------------------------------
    def test_case_05_bad_date_format(self):
        data = valid_run()
        data["start_date"] = "26/04/2026"        # dd/mm/yyyy instead of yyyy-mm-dd
        result = run(data)
        show(5, "start_date format is dd/mm/yyyy (invalid)", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 6 — start_date is not today
    # ------------------------------------------------------------------
    def test_case_06_date_not_today(self):
        data = valid_run()
        data["start_date"] = "2024-05-03"
        result = run(data)
        show(6, "start_date is a past date (not today)", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 7 — vehicle does not exist in DB
    # ------------------------------------------------------------------
    def test_case_07_vehicle_not_found(self):
        data = valid_run()
        data["vehicle_id"] = "ghost-vehicle"
        result = run(data)
        show(7, "vehicle_id not in Vehicle table", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 8 — operator does not exist in DB
    # ------------------------------------------------------------------
    def test_case_08_operator_not_found(self):
        data = valid_run()
        data["operator_id"] = "ghost-operator"
        result = run(data)
        show(8, "operator_id not in Operator table", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 9 — vehicle already in an active run
    # ------------------------------------------------------------------
    def test_case_09_vehicle_already_in_progress(self):
        Run.objects.create(
            vehicle=self.vehicle,
            operator=self.operator,
            route_id="r-test",
            trip_id="t-test",
            direction_id=0,
            shape_id="s-test",
            start_date=date.today(),
            run_status="IN_PROGRESS",
        )
        data = valid_run()
        result = run(data)
        show(9, "vehicle already has a run IN_PROGRESS", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 10 — no feed with is_current=True
    # ------------------------------------------------------------------
    def test_case_10_no_current_feed(self):
        Feed.objects.filter(feed_id="feed-test").update(is_current=False)
        data = valid_run()
        result = run(data)
        show(10, "no Feed with is_current=True exists", data, result, False)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # Case 11 — trip not found in current feed
    # ------------------------------------------------------------------
    def test_case_11_trip_not_in_feed(self):
        data = valid_run()
        data["trip_id"] = "trip-fantasma"
        result = run(data)
        show(11, "trip_id does not exist in current feed", data, result, False)
        self.assertFalse(result)
