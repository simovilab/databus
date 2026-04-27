import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from feed.models import Feed, Trip
from operations.models import Operator, Run, Vehicle

URL = "/api/run"


def show(case_num, description, status_code, body, expected_status):
    ok = "PASS" if status_code == expected_status else "FAIL"
    print(f"\n[{ok}] Case {case_num}: {description}")
    print(f"       Status : {status_code}  (expected {expected_status})")
    print(f"       Body   : {body}")


def valid_submitted():
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
        "run_status": "SUBMITTED",
    }


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class RunViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vehicle = Vehicle.objects.create(id="v-test", license_plate="TST-001")
        user = User.objects.create_user(username="op_test", password="pw")
        cls.operator = Operator.objects.create(id="op-test", user=user)
        cls.feed = Feed.objects.create(feed_id="feed-test", is_current=True)
        Trip.objects.bulk_create(
            [
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
            ]
        )

    def post(self, data):
        return self.client.post(
            URL, data=json.dumps(data), content_type="application/json"
        )

    def make_run(self, status):
        return Run.objects.create(
            vehicle=self.vehicle,
            operator=self.operator,
            route_id="r-test",
            trip_id="t-test",
            direction_id=0,
            shape_id="s-test",
            start_date=date.today(),
            run_status=status,
        )

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def test_case_01_get(self):
        response = self.client.get(URL)
        body = response.json()
        show(1, "GET /api/run → 200", response.status_code, body, 200)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body, {"message": "Hola"})

    # ------------------------------------------------------------------
    # POST SUBMITTED — válido → 200 con run_id
    # ------------------------------------------------------------------
    def test_case_02_submitted_valid(self):
        response = self.post(valid_submitted())
        body = response.json()
        show(2, "SUBMITTED valid → 200 + run_id", response.status_code, body, 200)
        self.assertEqual(response.status_code, 200)
        self.assertIn("run_id", body)

    # ------------------------------------------------------------------
    # POST SUBMITTED — trip no existe en el feed → 400
    # ------------------------------------------------------------------
    def test_case_03_submitted_trip_not_in_feed(self):
        data = valid_submitted()
        data["trip_id"] = "trip-fantasma"
        response = self.post(data)
        body = response.json()
        show(3, "SUBMITTED con trip inexistente → 400", response.status_code, body, 400)
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # POST SUBMITTED — validate_run falla (fecha no es hoy) → 400
    # ------------------------------------------------------------------
    def test_case_04_submitted_validation_fails(self):
        data = valid_submitted()
        data["start_date"] = "2024-05-03"
        response = self.post(data)
        body = response.json()
        show(
            4,
            "SUBMITTED fecha pasada → validate_run falla → 400",
            response.status_code,
            body,
            400,
        )
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # POST CONFIRMED — run_id válido → 200 IN_PROGRESS
    # ------------------------------------------------------------------
    def test_case_05_confirmed_valid(self):
        run = self.make_run("REGISTERED")
        response = self.post({"run_status": "CONFIRMED", "run_id": run.id})
        body = response.json()
        show(
            5,
            "CONFIRMED run_id válido → 200 IN_PROGRESS",
            response.status_code,
            body,
            200,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body.get("run_status"), "IN_PROGRESS")
        self.assertEqual(Run.objects.get(id=run.id).run_status, "IN_PROGRESS")

    # ------------------------------------------------------------------
    # POST CONFIRMED — run_id no existe → 404
    # ------------------------------------------------------------------
    def test_case_06_confirmed_run_not_found(self):
        response = self.post({"run_status": "CONFIRMED", "run_id": 99999})
        body = response.json()
        show(6, "CONFIRMED run_id inexistente → 404", response.status_code, body, 404)
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # POST COMPLETED — run IN_PROGRESS → 200 COMPLETED
    # ------------------------------------------------------------------
    def test_case_07_completed_valid(self):
        run = self.make_run("IN_PROGRESS")
        response = self.post({"run_status": "COMPLETED", "run_id": run.id})
        body = response.json()
        show(
            7,
            "COMPLETED run IN_PROGRESS → 200 COMPLETED",
            response.status_code,
            body,
            200,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body.get("run_status"), "COMPLETED")

    # ------------------------------------------------------------------
    # POST COMPLETED — run no está IN_PROGRESS → 400
    # ------------------------------------------------------------------
    def test_case_08_completed_run_not_in_progress(self):
        run = self.make_run("REGISTERED")
        response = self.post({"run_status": "COMPLETED", "run_id": run.id})
        body = response.json()
        show(8, "COMPLETED run no IN_PROGRESS → 400", response.status_code, body, 400)
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # POST — run_status desconocido → 400
    # ------------------------------------------------------------------
    def test_case_09_unknown_run_status(self):
        response = self.post({"run_status": "INVENTED"})
        body = response.json()
        show(9, "run_status desconocido → 400", response.status_code, body, 400)
        self.assertEqual(response.status_code, 400)


class LoginViewTest(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "testpassword"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )
        Operator.objects.create(id="op-login-test", user=self.user)
        self.url = reverse("login")

    def test_login_success(self):
        response = self.client.post(
            self.url, {"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn("token", response_data)
        print(f"Token: {response_data['token']}")

    def test_login_failure(self):
        response = self.client.post(
            self.url, {"username": self.username, "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
