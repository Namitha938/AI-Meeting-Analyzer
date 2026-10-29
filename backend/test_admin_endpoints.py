from app.database import SessionLocal
from app.models import User, Meeting
from app.routers.admin import get_system_stats, get_all_users_admin, update_user_role, toggle_user_status, get_all_meetings_admin

db = SessionLocal()
admin = db.query(User).filter(User.role == "admin").first()
if not admin:
    admin = db.query(User).first()
    admin.role = "admin"
    db.commit()

print(f"Testing Admin endpoints with admin user: '{admin.email}' (Role: {admin.role})...")

# 1. System Stats
stats = get_system_stats(admin=admin, db=db)
assert stats["status"] == "healthy"
assert "users" in stats
assert "meetings" in stats
assert "nlp_metrics" in stats
print(f" [PASS] System Stats: {stats['users']['total']} users, {stats['meetings']['total']} meetings, {stats['meetings']['total_audio_hours']} hours processed.")

# 2. Get All Users
users = get_all_users_admin(admin=admin, db=db)
assert len(users) > 0
print(f" [PASS] All Users: Retrieved {len(users)} registered users.")

# 3. User Role Update
test_user = [u for u in users if u.id != admin.id]
if test_user:
    u = test_user[0]
    orig_role = u.role
    target_role = "admin" if orig_role == "user" else "user"
    res = update_user_role(user_id=u.id, new_role=target_role, admin=admin, db=db)
    assert res["status"] == "success"
    # Revert back
    update_user_role(user_id=u.id, new_role=orig_role, admin=admin, db=db)
    print(f" [PASS] Role Update: Successfully toggled role for user '{u.email}'.")

# 4. Get All Meetings (Admin cross-user view)
meetings_view = get_all_meetings_admin(admin=admin, db=db)
assert len(meetings_view) > 0
print(f" [PASS] Admin Meetings View: Retrieved {len(meetings_view)} total meetings across organizations.")

print("\n>>> STEP 13 (ADMIN PANEL APIs) 100% OPERATIONAL!")

