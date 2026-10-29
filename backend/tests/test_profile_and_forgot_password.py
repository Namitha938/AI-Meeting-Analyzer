import unittest
import os
import io
import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash, verify_password

class TestProfileAndForgotPassword(unittest.TestCase):
    def setUp(self):
        self.db: Session = SessionLocal()
        # Ensure a test user exists
        test_email = "test_profile_user@meetora.ai"
        user = self.db.query(User).filter(User.email == test_email).first()
        if not user:
            user = User(
                email=test_email,
                hashed_password=get_password_hash("initialpassword123"),
                full_name="Alex Turner",
                role="user",
                job_title="ML Researcher",
                is_active=True,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        self.user = user

    def tearDown(self):
        self.db.close()

    def test_profile_update_persistence(self):
        """Verify updating user profile information persists to database."""
        self.user.full_name = "Alex Turner PhD"
        self.user.job_title = "Principal AI Scientist"
        self.user.avatar_url = "https://images.unsplash.com/photo-1534528741775-53994a69daeb"
        self.db.commit()
        self.db.refresh(self.user)

        updated = self.db.query(User).filter(User.email == "test_profile_user@meetora.ai").first()
        self.assertIsNotNone(updated)
        self.assertEqual(updated.full_name, "Alex Turner PhD")
        self.assertEqual(updated.job_title, "Principal AI Scientist")
        self.assertEqual(updated.avatar_url, "https://images.unsplash.com/photo-1534528741775-53994a69daeb")

    def test_forgot_and_reset_password_flow(self):
        """Verify token generation, token expiry, and password reset."""
        import secrets
        token = secrets.token_urlsafe(32)
        expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        
        self.user.reset_token = token
        self.user.reset_token_expiry = expiry
        self.db.commit()

        # Check token stored
        found_user = self.db.query(User).filter(
            User.reset_token == token,
            User.reset_token_expiry > datetime.datetime.utcnow()
        ).first()
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.email, "test_profile_user@meetora.ai")

        # Now simulate resetting password
        new_raw_pwd = "newSuperSecretPassword2026!"
        found_user.hashed_password = get_password_hash(new_raw_pwd)
        found_user.reset_token = None
        found_user.reset_token_expiry = None
        self.db.commit()

        # Verify old password fails and new password verifies
        refreshed = self.db.query(User).filter(User.email == "test_profile_user@meetora.ai").first()
        self.assertFalse(verify_password("initialpassword123", refreshed.hashed_password))
        self.assertTrue(verify_password(new_raw_pwd, refreshed.hashed_password))
        self.assertIsNone(refreshed.reset_token)

if __name__ == '__main__':
    unittest.main()

