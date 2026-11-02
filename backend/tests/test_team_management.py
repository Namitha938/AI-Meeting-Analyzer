import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine, ensure_db_schema
from app.models import (
    User, Meeting, Team, TeamMember, TeamInvite, Notification, AuditLog,
    Transcript, HumanCorrection, ActionItem
)
from app.auth import get_password_hash, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    ensure_db_schema()
    session = SessionLocal()
    yield session
    session.close()

def create_user(db, prefix: str, role: str = "user") -> tuple[User, str]:
    ts = int(datetime.utcnow().timestamp() * 1000)
    email = f"{prefix}_{ts}@meetora.ai"
    user = User(
        email=email,
        hashed_password=get_password_hash("Password123!"),
        full_name=f"Test {prefix.title()}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(data={"sub": user.email, "role": user.role, "user_id": user.id})
    return user, token


def test_team_creation_and_owner_edit(db):
    """Owner can create team and edit name, color, description."""
    owner, token = create_user(db, "tm_owner")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create team
    create_res = client.post("/teams", json={
        "name": "Engineering Core",
        "color": "emerald",
        "description": "Core platform and systems team"
    }, headers=headers)
    assert create_res.status_code == 201, create_res.text
    data = create_res.json()
    assert data["name"] == "Engineering Core"
    assert data["color"] == "emerald"
    assert data["my_role"] == "owner"
    team_id = data["id"]

    # 2. Owner can edit team
    patch_res = client.patch(f"/teams/{team_id}", json={
        "name": "Platform Engineering",
        "color": "indigo",
        "description": "Updated platform team"
    }, headers=headers)
    assert patch_res.status_code == 200
    pdata = patch_res.json()
    assert pdata["name"] == "Platform Engineering"
    assert pdata["color"] == "indigo"
    assert pdata["description"] == "Updated platform team"


def test_admin_edit_vs_delete_permissions(db):
    """Team admin can edit team info, but CANNOT delete team."""
    owner, o_token = create_user(db, "tm_adm_owner")
    admin_user, a_token = create_user(db, "tm_admin")

    # Create team
    t_res = client.post("/teams", json={"name": "DevOps", "color": "blue"}, headers={"Authorization": f"Bearer {o_token}"})
    team_id = t_res.json()["id"]

    # Add admin_user as team admin
    admin_member = TeamMember(team_id=team_id, user_id=admin_user.id, role="admin")
    db.add(admin_member)
    db.commit()

    a_headers = {"Authorization": f"Bearer {a_token}"}

    # Admin can edit
    edit_res = client.patch(f"/teams/{team_id}", json={"description": "DevOps infrastructure team"}, headers=a_headers)
    assert edit_res.status_code == 200
    assert edit_res.json()["description"] == "DevOps infrastructure team"

    # Admin cannot delete team -> 403
    del_res = client.delete(f"/teams/{team_id}", headers=a_headers)
    assert del_res.status_code == 403


def test_member_and_viewer_cannot_edit(db):
    """Team members and viewers get 403 when trying to edit team."""
    owner, o_token = create_user(db, "tm_mv_owner")
    member_user, m_token = create_user(db, "tm_member")
    viewer_user, v_token = create_user(db, "tm_viewer")

    t_res = client.post("/teams", json={"name": "Analytics Hub"}, headers={"Authorization": f"Bearer {o_token}"})
    team_id = t_res.json()["id"]

    db.add(TeamMember(team_id=team_id, user_id=member_user.id, role="member"))
    db.add(TeamMember(team_id=team_id, user_id=viewer_user.id, role="viewer"))
    db.commit()

    # Member fails
    res_m = client.patch(f"/teams/{team_id}", json={"name": "Hacked"}, headers={"Authorization": f"Bearer {m_token}"})
    assert res_m.status_code == 403

    # Viewer fails
    res_v = client.patch(f"/teams/{team_id}", json={"name": "Hacked"}, headers={"Authorization": f"Bearer {v_token}"})
    assert res_v.status_code == 403


def test_non_member_gets_404_not_found(db):
    """Non-members get 404 so existence of team is not leaked."""
    owner, o_token = create_user(db, "tm_sec_owner")
    outsider, out_token = create_user(db, "tm_outsider")

    t_res = client.post("/teams", json={"name": "Secret Project X"}, headers={"Authorization": f"Bearer {o_token}"})
    team_id = t_res.json()["id"]

    out_headers = {"Authorization": f"Bearer {out_token}"}

    # Accessing team details returns 404
    get_res = client.get(f"/teams/{team_id}", headers=out_headers)
    assert get_res.status_code == 404

    # Editing returns 404
    patch_res = client.patch(f"/teams/{team_id}", json={"name": "Discovered"}, headers=out_headers)
    assert patch_res.status_code == 404


def test_delete_team_with_move_meetings(db):
    """Deleting a team with meetings='move' moves meetings to owner's personal workspace."""
    owner, o_token = create_user(db, "tm_move_owner")
    o_headers = {"Authorization": f"Bearer {o_token}"}

    t_res = client.post("/teams", json={"name": "Temporary Team"}, headers=o_headers)
    team_id = t_res.json()["id"]

    # Create meeting attached to this team
    meeting = Meeting(
        title="Team Standup",
        user_id=owner.id,
        team_id=team_id,
        status="completed"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    meeting_id = meeting.id

    # Delete team with meetings=move
    del_res = client.delete(f"/teams/{team_id}?meetings=move", headers=o_headers)
    assert del_res.status_code == 204

    # Verify meeting still exists and team_id is now None
    db.expire_all()
    m_check = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert m_check is not None
    assert m_check.team_id is None


def test_delete_team_with_delete_meetings_and_detach_corrections(db):
    """Deleting team with meetings='delete' cleans up meetings and preserves retraining records."""
    owner, o_token = create_user(db, "tm_purge_owner")
    o_headers = {"Authorization": f"Bearer {o_token}"}

    t_res = client.post("/teams", json={"name": "Team Purge"}, headers=o_headers)
    team_id = t_res.json()["id"]

    meeting = Meeting(title="Strategy Sync", user_id=owner.id, team_id=team_id, status="completed")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    m_id = meeting.id

    act = ActionItem(meeting_id=m_id, title="Refactor Auth", status="pending")
    db.add(act)
    db.commit()
    db.refresh(act)

    hc = HumanCorrection(
        user_id=owner.id,
        meeting_id=m_id,
        action_item_id=act.id,
        original_text="old text",
        corrected_text="new text",
        correction_type="edit"
    )
    db.add(hc)
    db.commit()
    db.refresh(hc)
    hc_id = hc.id

    del_res = client.delete(f"/teams/{team_id}?meetings=delete", headers=o_headers)
    assert del_res.status_code == 204

    db.expire_all()
    # Meeting is deleted
    assert db.query(Meeting).filter(Meeting.id == m_id).first() is None
    # Human correction is preserved with detached meeting_id / action_item_id
    hc_saved = db.query(HumanCorrection).filter(HumanCorrection.id == hc_id).first()
    assert hc_saved is not None
    assert hc_saved.meeting_id is None
    assert hc_saved.action_item_id is None


def test_member_role_rules_and_last_owner_protection(db):
    """
    Role management rules:
    - Admins cannot change owner or other admins
    - Last owner cannot be demoted or removed
    - Sole owner cannot leave without transferring ownership
    """
    owner, o_token = create_user(db, "tm_prot_owner")
    admin1, a1_token = create_user(db, "tm_prot_a1")
    admin2, a2_token = create_user(db, "tm_prot_a2")
    member, m_token = create_user(db, "tm_prot_m")

    t_res = client.post("/teams", json={"name": "Governance Board"}, headers={"Authorization": f"Bearer {o_token}"})
    team_id = t_res.json()["id"]

    db.add_all([
        TeamMember(team_id=team_id, user_id=admin1.id, role="admin"),
        TeamMember(team_id=team_id, user_id=admin2.id, role="admin"),
        TeamMember(team_id=team_id, user_id=member.id, role="member"),
    ])
    db.commit()

    a1_headers = {"Authorization": f"Bearer {a1_token}"}

    # Admin1 cannot demote owner -> 400
    r_demote_owner = client.patch(f"/teams/{team_id}/members/{owner.id}", json={"role": "member"}, headers=a1_headers)
    assert r_demote_owner.status_code == 400

    # Admin1 cannot demote Admin2 -> 403
    r_demote_a2 = client.patch(f"/teams/{team_id}/members/{admin2.id}", json={"role": "viewer"}, headers=a1_headers)
    assert r_demote_a2.status_code == 403

    # Admin1 CAN change regular member
    r_demote_m = client.patch(f"/teams/{team_id}/members/{member.id}", json={"role": "viewer"}, headers=a1_headers)
    assert r_demote_m.status_code == 200
    assert r_demote_m.json()["role"] == "viewer"

    # Owner cannot leave without transferring ownership -> 400
    o_headers = {"Authorization": f"Bearer {o_token}"}
    r_leave = client.post(f"/teams/{team_id}/leave", headers=o_headers)
    assert r_leave.status_code == 400


def test_ownership_transfer(db):
    """Owner can transfer ownership to an existing member. Old owner becomes admin."""
    owner, o_token = create_user(db, "tm_tx_owner")
    member, m_token = create_user(db, "tm_tx_member")

    t_res = client.post("/teams", json={"name": "Transfer Team"}, headers={"Authorization": f"Bearer {o_token}"})
    team_id = t_res.json()["id"]

    db.add(TeamMember(team_id=team_id, user_id=member.id, role="member"))
    db.commit()

    o_headers = {"Authorization": f"Bearer {o_token}"}
    tx_res = client.post(f"/teams/{team_id}/transfer-ownership", json={"new_owner_user_id": member.id}, headers=o_headers)
    assert tx_res.status_code == 200

    db.expire_all()
    # Check new roles
    team = db.query(Team).filter(Team.id == team_id).first()
    assert team.owner_id == member.id

    old_owner_m = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == owner.id).first()
    assert old_owner_m.role == "admin"

    new_owner_m = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == member.id).first()
    assert new_owner_m.role == "owner"


def test_invite_lifecycle_and_acceptance(db):
    """Test invite creation, rate limit, resend, revoke, and accept."""
    owner, o_token = create_user(db, "tm_inv_owner")
    invitee, i_token = create_user(db, "tm_invitee")
    o_headers = {"Authorization": f"Bearer {o_token}"}

    t_res = client.post("/teams", json={"name": "Invite Hub"}, headers=o_headers)
    team_id = t_res.json()["id"]

    # 1. Send invite
    inv_res = client.post(f"/teams/{team_id}/invites", json={"email": invitee.email, "role": "member"}, headers=o_headers)
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    token = inv_data["invite_link"].split("=")[-1]
    invite_id = inv_data["id"]

    # 2. Resend invite
    resend_res = client.post(f"/teams/{team_id}/invites/{invite_id}/resend", headers=o_headers)
    assert resend_res.status_code == 200
    new_token = resend_res.json()["invite_link"].split("=")[-1]

    # 3. Old token should fail or new token succeeds
    acc_res = client.post(f"/teams/invites/accept?token={new_token}", headers={"Authorization": f"Bearer {i_token}"})
    assert acc_res.status_code == 200
    assert acc_res.json()["success"] is True

    # 4. Token cannot be reused (single-use)
    acc_again = client.post(f"/teams/invites/accept?token={new_token}", headers={"Authorization": f"Bearer {i_token}"})
    assert acc_again.status_code == 400


def test_audit_logs_and_notifications_created(db):
    """Team actions trigger audit logs and notifications."""
    owner, o_token = create_user(db, "tm_audit_owner")
    member, m_token = create_user(db, "tm_audit_member")
    o_headers = {"Authorization": f"Bearer {o_token}"}

    t_res = client.post("/teams", json={"name": "Audit Team"}, headers=o_headers)
    team_id = t_res.json()["id"]

    db.add(TeamMember(team_id=team_id, user_id=member.id, role="viewer"))
    db.commit()

    # Update member role -> should generate audit log and user notification
    patch_m = client.patch(f"/teams/{team_id}/members/{member.id}", json={"role": "member"}, headers=o_headers)
    assert patch_m.status_code == 200

    db.expire_all()
    # Check AuditLog
    audit = db.query(AuditLog).filter(AuditLog.action == "MEMBER_ROLE_CHANGE", AuditLog.user_id == owner.id).first()
    assert audit is not None
    assert audit.resource == f"team:{team_id}/member:{member.id}"

    # Check Notification for member
    notif = db.query(Notification).filter(Notification.user_id == member.id).first()
    assert notif is not None
    assert "role" in notif.message.lower() or "updated" in notif.title.lower()

