from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

# Create your tests here.


class LoginViewTest(TestCase):
    def setUp(self):
        # Create a test user
        self.username = "testuser"
        self.password = "testpassword"
        self.user = User.objects.create_user(
            username=self.username, password=self.password
        )
        self.url = reverse("login")

    def test_login_success(self):
        # Test successful login
        response = self.client.post(
            self.url, {"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn("token", response_data)
        print(f"Token: {response_data['token']}")

    def test_login_failure(self):
        # Test login failure with incorrect credentials
        response = self.client.post(
            self.url, {"username": self.username, "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.json())
