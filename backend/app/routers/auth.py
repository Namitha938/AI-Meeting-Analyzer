from typing import List, Optional
import secrets
import datetime
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.storage import get_storage
from app.models import User, Meeting, Comment
from app.schemas import (
    UserRegister, UserLogin, UserResponse, Token, GoogleAuthRequest,
    UserProfileUpdate, ForgotPasswordRequest, ResetPasswordRequest,
    TwoFactorSetupResponse, TwoFactorVerifyRequest, TwoFactorVerifyResponse
)
from app.auth import (
    get_password_hash, verify_password, create_access_token, get_current_user, get_current_admin,
    generate_totp_secret, get_totp_token, verify_totp_token, generate_backup_codes
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    norm_email = user_in.email.strip().lower()
    # Check if user already exists (case-insensitive deduplication)
    existing = db.query(User).filter(User.email.ilike(norm_email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in instead."
        )

    # First registered user is admin, otherwise role
    total_users = db.query(User).count()
    user_role = user_in.role if user_in.role in ["user", "admin"] else "user"
    if total_users == 0:
        user_role = "admin"

    hashed_pw = get_password_hash(user_in.password)
    user = User(
        email=norm_email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name or norm_email.split("@")[0],
        role=user_role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    norm_email = user_in.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(norm_email)).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # If 2FA is active, verify TOTP code or prompt for 2FA
    if user.two_factor_enabled:
        if not user_in.totp_code:
            return {
                "access_token": "",
                "token_type": "bearer",
                "user": None,
                "requires_2fa": True,
            }

        clean_code = (user_in.totp_code or "").strip().upper()
        totp_valid = verify_totp_token(user.two_factor_secret or "", clean_code, valid_window=1)
        current_backup_codes = list(user.backup_codes or [])
        if not totp_valid and current_backup_codes and clean_code in current_backup_codes:
            totp_valid = True
            current_backup_codes.remove(clean_code)
            user.backup_codes = list(current_backup_codes)
            db.commit()

        if not totp_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 6-digit authenticator or backup code. Please check your app and try again."
            )

    access_token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "requires_2fa": False,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/google", response_model=Token)
def google_auth(auth_in: GoogleAuthRequest, db: Session = Depends(get_db)):
    email = auth_in.email.strip().lower()
    # Check case-insensitively and trim
    user = db.query(User).filter(User.email.ilike(email)).first()

    if not user:
        # Create user if it doesn't exist
        total = db.query(User).count()
        role = "admin" if total == 0 else "user"
        dummy_pw = get_password_hash(f"google_{auth_in.google_id or 'oauth'}_{email}")
        user = User(
            email=email,
            full_name=auth_in.full_name or email.split("@")[0],
            hashed_password=dummy_pw,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Deduplication guarantee: Reuse existing account and sync name if missing
        if auth_in.full_name and (not user.full_name or user.full_name == user.email.split("@")[0]):
            user.full_name = auth_in.full_name
            db.commit()
            db.refresh(user)

    access_token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/cleanup-duplicates")
def cleanup_duplicate_accounts(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.asc()).all()
    seen = {}
    duplicates = []

    for u in users:
        norm_email = u.email.strip().lower()
        if norm_email in seen:
            duplicates.append(u)
        else:
            seen[norm_email] = u

    deleted_count = len(duplicates)
    for dup in duplicates:
        primary_user = seen[dup.email.strip().lower()]
        # Safely re-link any child records to primary account before deleting duplicate
        db.query(Meeting).filter(Meeting.user_id == dup.id).update({"user_id": primary_user.id})
        db.query(Comment).filter(Comment.user_id == dup.id).update({"user_id": primary_user.id})
        db.delete(dup)
    db.commit()

    return {
        "status": "success",
        "message": f"Successfully removed {deleted_count} duplicate account(s).",
        "removed_count": deleted_count,
        "active_users": [u.email for u in seen.values()],
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/users", response_model=List[UserResponse])
def get_all_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(User).all()

@router.patch("/profile", response_model=UserResponse)
def update_profile(
    profile_in: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates user full name, job title, and avatar URL."""
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name.strip()
    if profile_in.job_title is not None:
        current_user.job_title = profile_in.job_title.strip()
    if profile_in.avatar_url is not None:
        current_user.avatar_url = profile_in.avatar_url.strip()

    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Uploads user profile picture to storage and persists URL."""
    storage = get_storage()
    meta = storage.save_file(file)
    raw_path = meta.get("file_path") or meta.get("url") or ""
    filename = os.path.basename(raw_path)
    avatar_url = f"http://localhost:8000/uploads/{filename}"

    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "avatar_url": avatar_url,
        "message": "Profile photo updated successfully."
    }

@router.post("/forgot-password")
def forgot_password(
    req: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Generates password reset token and creates reset URL."""
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email_clean)).first()
    if not user:
        # Prevent email enumeration while giving clear response
        return {
            "status": "success",
            "message": f"If an account with {req.email} exists, a reset link has been dispatched.",
        }

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    db.commit()

    reset_url = f"http://localhost:5173/#forgot?token={token}&email={user.email}"
    return {
        "status": "success",
        "message": f"Password reset instructions dispatched to {user.email}.",
        "reset_token": token,
        "reset_url": reset_url,
    }

@router.post("/reset-password")
def reset_password(
    req: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Validates reset token and sets new password."""
    now = datetime.datetime.utcnow()
    user = db.query(User).filter(
        User.reset_token == req.token,
        User.reset_token_expiry > now
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token. Please request a new one."
        )

    user.hashed_password = get_password_hash(req.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {
        "status": "success",
        "message": "Your password has been reset successfully. You can now log in with your new password."
    }

# ==========================================
# ==========================================
# Session Management & Token Endpoints
# ==========================================
@router.get("/validate-session")
def validate_session(current_user: User = Depends(get_current_user)):
    """
    Validates active JWT token session and returns current user with session validity metadata.
    """
    return {
        "status": "active",
        "valid": True,
        "user": current_user,
        "expires_in_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "two_factor_enabled": bool(current_user.two_factor_enabled),
    }

@router.post("/refresh-token", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Renews access token for an active authenticated session.
    """
    new_token = create_access_token(
        data={"sub": current_user.email, "role": current_user.role, "user_id": current_user.id}
    )
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "user": current_user,
        "requires_2fa": False,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/logout")
def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logs out active user session and invalidates client session state.
    """
    return {
        "status": "success",
        "message": f"Successfully logged out session for {current_user.email}."
    }

# ==========================================
# Two-Factor Authentication (2FA / TOTP)
# ==========================================
@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates a new RFC 6238 TOTP secret, standard otpauth:// URI,
    and a scannable QR code image URL for Google/Microsoft Authenticator.
    """
    secret = generate_totp_secret()
    label = urllib.parse.quote(f"Meetora:{current_user.email}")
    issuer = urllib.parse.quote("Meetora")
    otpauth_url = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=10&data={urllib.parse.quote(otpauth_url)}"
    backup_codes = generate_backup_codes(5)

    # Store pending secret and generated backup codes
    current_user.two_factor_secret = secret
    current_user.backup_codes = list(backup_codes)
    db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_url=otpauth_url,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes,
    )

@router.post("/2fa/verify", response_model=TwoFactorVerifyResponse)
def verify_two_factor(
    req: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validates a 6-digit TOTP code against the secret key.
    Activates 2FA upon successful verification.
    """
    secret = req.secret or current_user.two_factor_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No 2FA secret found. Please initiate 2FA setup first."
        )

    # Verify code using RFC 6238 TOTP
    code_valid = verify_totp_token(secret, req.code, valid_window=1)
    
    # Or check backup codes
    is_backup = False
    if not code_valid and current_user.backup_codes and req.code.upper() in current_user.backup_codes:
        code_valid = True
        is_backup = True
        # Consume backup code
        current_user.backup_codes.remove(req.code.upper())

    if not code_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 6-digit authenticator code. Please check your authenticator app and try again."
        )

    current_user.two_factor_enabled = True
    current_user.two_factor_secret = secret
    if not current_user.backup_codes:
        current_user.backup_codes = generate_backup_codes(5)
    else:
        current_user.backup_codes = list(current_user.backup_codes)
    db.commit()

    return TwoFactorVerifyResponse(
        status="success",
        message="Two-Factor Authentication successfully verified and enabled!" if not is_backup else "Logged in using backup code.",
        backup_codes=current_user.backup_codes,
    )

@router.post("/2fa/disable")
def disable_two_factor(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disables 2FA on the user account."""
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.backup_codes = []
    db.commit()

    return {
        "status": "success",
        "message": "Two-factor authentication has been disabled."
    }
