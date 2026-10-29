import unittest
from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash, verify_password, create_access_token

class TestAuthAndRBAC(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_password_hashing_and_verification(self):
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_jwt_token_generation(self):
        data = {"sub": "jordan@meetora.ai", "role": "admin", "user_id": 1}
        token = create_access_token(data=data)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 30)

    def test_user_database_model(self):
        admin = self.db.query(User).filter(User.role == "admin").first()
        self.assertIsNotNone(admin, "At least one admin user should exist in database")
        self.assertEqual(admin.role, "admin")
        self.assertTrue(admin.is_active)

if __name__ == "__main__":
    unittest.main()

