import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash

class TestGoogleAuth(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()
        # Clean up any test users
        self.test_emails = [
            "google_test_new@meetora.ai",
            "google_test_existing@meetora.ai",
            "google_test_disabled@meetora.ai",
        ]
        for email in self.test_emails:
            self.db.query(User).filter(User.email == email).delete()
        self.db.commit()

    def tearDown(self):
        for email in self.test_emails:
            self.db.query(User).filter(User.email == email).delete()
        self.db.commit()
        self.db.close()

    def test_google_auth_new_user(self):
        payload = {
            "email": "google_test_new@meetora.ai",
            "full_name": "New Google User",
            "google_id": "google-12345",
            "avatar": "https://example.com/avatar.png"
        }
        res = self.client.post("/api/auth/google", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["email"], "google_test_new@meetora.ai")
        self.assertEqual(data["user"]["full_name"], "New Google User")

        # Verify DB record
        user = self.db.query(User).filter(User.email == "google_test_new@meetora.ai").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.avatar_url, "https://example.com/avatar.png")

    def test_google_auth_existing_user_deduplication(self):
        # Create user beforehand
        user = User(
            email="google_test_existing@meetora.ai",
            hashed_password=get_password_hash("ExistingPassword123!"),
            full_name="Original Name",
            role="user",
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()

        # Login with Google
        payload = {
            "email": "google_test_existing@meetora.ai",
            "full_name": "Original Name",
            "google_id": "google-existing-999"
        }
        res = self.client.post("/api/auth/google", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)

        # Confirm count remains 1 (no duplicate created)
        count = self.db.query(User).filter(User.email == "google_test_existing@meetora.ai").count()
        self.assertEqual(count, 1)

    def test_google_auth_empty_email_validation(self):
        payload = {
            "email": "   ",
            "full_name": "No Email",
        }
        res = self.client.post("/api/auth/google", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_google_auth_disabled_account(self):
        user = User(
            email="google_test_disabled@meetora.ai",
            hashed_password=get_password_hash("Disabled123!"),
            full_name="Disabled User",
            role="user",
            is_active=False,
        )
        self.db.add(user)
        self.db.commit()

        payload = {
            "email": "google_test_disabled@meetora.ai",
            "google_id": "google-disabled-000"
        }
        res = self.client.post("/api/auth/google", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("disabled", res.json()["detail"].lower())

    def test_google_auth_root_route_alias(self):
        payload = {
            "email": "google_test_new@meetora.ai",
            "full_name": "New Google User",
            "google_id": "google-12345"
        }
        res = self.client.post("/auth/google", json=payload)
        self.assertEqual(res.status_code, 200)

if __name__ == "__main__":
    unittest.main()

