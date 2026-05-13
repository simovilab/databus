from django.test import TestCase
from django.urls import reverse


class RunsViewSetTests(TestCase):
    def test_runs_get_returns_200(self):
        response = self.client.get(reverse("runs"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Hello world!"})
