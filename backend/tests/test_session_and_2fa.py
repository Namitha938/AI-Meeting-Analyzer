import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine
from app.models import User
from app.auth import get_password_hash, create_access_token, get_totp_token

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_session_validation_and_refresh(db):
    """Test /auth/validate-session and /auth/refresh-token."""
    email = f"session_test_{int(datetime.now().timestamp())}@meetora.ai"
    user = User(
        email=email,
        hashed_password=get_password_hash("SessionPass123!"),
        full_name="Session Tester",
        role="user",
        is_active=True
    )
    db.add(user)
    db.commit()

    # 1. Unauthenticated request to /auth/validate-session should return 401
    unauth_res = client.get("/auth/validate-session")
    assert unauth_res.status_code == 401

    # 2. Login to get token
    login_res = client.post("/auth/login", json={"email": email, "password": "SessionPass123!"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token

    # 3. Authenticated validate-session
    val_res = client.get("/auth/validate-session", headers={"Authorization": f"Bearer {token}"})
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["status"] == "active"
    assert val_data["valid"] is True
    assert val_data["user"]["email"] == email

    # 4. Refresh token
    refresh_res = client.post("/auth/refresh-token", headers={"Authorization": f"Bearer {token}"})
    assert refresh_res.status_code == 200
    new_token = refresh_res.json()["access_token"]
    assert new_token
    assert new_token != ""

    # 5. Logout endpoint
    logout_res = client.post("/auth/logout", headers={"Authorization": f"Bearer {new_token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "success"

def test_two_factor_authentication_full_lifecycle(db):
    """Test 2FA setup, verification, login with TOTP, login with backup codes, and disable."""
    email = f"twofa_test_{int(datetime.now().timestamp())}@meetora.ai"
    user = User(
        email=email,
        hashed_password=get_password_hash("TwoFactorPass123!"),
        full_name="TwoFA Tester",
        role="user",
        is_active=True,
        two_factor_enabled=False
    )
    db.add(user)
    db.commit()

    token = create_access_token(data={"sub": email, "role": "user", "user_id": user.id})

    # 1. Setup 2FA
    setup_res = client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
    assert setup_res.status_code == 200
    setup_data = setup_res.json()
    secret = setup_data["secret"]
    assert secret
    assert "otpauth://" in setup_data["otpauth_url"]
    assert "create-qr-code" in setup_data["qr_code_url"]
    assert len(setup_data["backup_codes"]) == 5
    backup_codes = setup_data["backup_codes"]

    # 2. Verify with wrong code -> should fail
    verify_fail = client.post(
        "/auth/2fa/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "000000", "secret": secret}
    )
    assert verify_fail.status_code == 400

    # 3. Verify with valid TOTP code
    valid_code = get_totp_token(secret)
    verify_ok = client.post(
        "/auth/2fa/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": valid_code, "secret": secret}
    )
    assert verify_ok.status_code == 200
    assert verify_ok.json()["status"] == "success"

    # Refresh user from DB to verify two_factor_enabled
    db.refresh(user)
    assert user.two_factor_enabled is True

    # 4. Login without code -> should return requires_2fa: True
    login_no_code = client.post("/auth/login", json={"email": email, "password": "TwoFactorPass123!"})
    assert login_no_code.status_code == 200
    assert login_no_code.json()["requires_2fa"] is True
    assert login_no_code.json()["access_token"] == ""

    # 5. Login with wrong code -> should fail 400
    login_wrong_code = client.post(
        "/auth/login",
        json={"email": email, "password": "TwoFactorPass123!", "totp_code": "999999"}
    )
    assert login_wrong_code.status_code == 400

    # 6. Login with fresh TOTP code
    fresh_code = get_totp_token(secret)
    login_ok = client.post(
        "/auth/login",
        json={"email": email, "password": "TwoFactorPass123!", "totp_code": fresh_code}
    )
    assert login_ok.status_code == 200
    assert login_ok.json()["requires_2fa"] is False
    assert login_ok.json()["access_token"] != ""

    # 7. Login with single-use backup code
    used_backup_code = backup_codes[0]
    login_backup = client.post(
        "/auth/login",
        json={"email": email, "password": "TwoFactorPass123!", "totp_code": used_backup_code}
    )
    assert login_backup.status_code == 200
    assert login_backup.json()["access_token"] != ""

    # 8. Re-using the same backup code must fail
    login_backup_reuse = client.post(
        "/auth/login",
        json={"email": email, "password": "TwoFactorPass123!", "totp_code": used_backup_code}
    )
    assert login_backup_reuse.status_code == 400

    # 9. Disable 2FA
    disable_res = client.post("/auth/2fa/disable", headers={"Authorization": f"Bearer {token}"})
    assert disable_res.status_code == 200
    db.refresh(user)
    assert user.two_factor_enabled is False
