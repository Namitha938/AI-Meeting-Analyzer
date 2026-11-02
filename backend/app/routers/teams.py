import datetime
import secrets
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import (
    User, Team, TeamMember, TeamInvite, Notification, AuditLog, Meeting
)
from app.schemas import (
    TeamCreate, TeamUpdate, TeamResponse,
    TeamMemberResponse, TeamMemberRoleUpdate,
    TeamTransferOwnershipRequest, TeamInviteCreate, TeamInviteResponse,
    NotificationResponse
)
from app.auth import get_current_user
from app.routers.meetings import perform_delete_meeting

logger = logging.getLogger("meetora.teams")

router = APIRouter(prefix="/teams", tags=["Teams"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ==============================================================================
# Helper functions
# ==============================================================================

def log_team_audit(
    db: Session,
    user: User,
    action: str,
    resource: str,
    details: dict,
    status: str = "SUCCESS",
    severity: str = "INFO"
):
    """Creates an audit log entry for team actions."""
    try:
        entry = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=action,
            resource=resource,
            status=status,
            severity=severity,
            details=details,
            created_at=datetime.datetime.utcnow()
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        db.rollback()


def create_user_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "team"
):
    """Creates an in-app notification for a user."""
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            read=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")
        db.rollback()


def get_team_and_role(team_id: int, current_user: User, db: Session):
    """
    Checks membership and returns (team, user_role).
    If user is site-wide admin, user_role defaults to 'owner' privileges if not in team.
    If user is NOT a member and not site-wide admin, returns 404 (does NOT leak team existence).
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()

    if member:
        return team, member.role

    # Site-wide admin check
    if getattr(current_user, "role", "") == "admin":
        return team, "owner"

    # User is not a member -> Return 404 to avoid leaking existence
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")


# ==============================================================================
# Team CRUD Endpoints
# ==============================================================================

@router.get("", response_model=List[TeamResponse])
def list_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all teams that the current user belongs to (or all if site-wide admin)."""
    if getattr(current_user, "role", "") == "admin":
        teams = db.query(Team).order_by(Team.created_at.desc()).all()
    else:
        member_team_ids = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).all()
        team_ids = [t[0] for t in member_team_ids]
        teams = db.query(Team).filter(Team.id.in_(team_ids)).order_by(Team.created_at.desc()).all()

    results = []
    for team in teams:
        member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
        membership = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.user_id == current_user.id
        ).first()

        my_role = membership.role if membership else ("owner" if getattr(current_user, "role", "") == "admin" else "viewer")
        results.append(TeamResponse(
            id=team.id,
            name=team.name,
            color=team.color or "violet",
            description=team.description,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at,
            member_count=member_count,
            my_role=my_role
        ))

    return results


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    team_in: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new team. Creator automatically becomes the owner."""
    # Check uniqueness per owner
    existing = db.query(Team).filter(
        Team.owner_id == current_user.id,
        Team.name == team_in.name.strip()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already own a team named '{team_in.name.strip()}'"
        )

    team = Team(
        name=team_in.name.strip(),
        color=team_in.color or "violet",
        description=team_in.description,
        owner_id=current_user.id,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    # Add creator as owner member
    owner_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role="owner",
        joined_at=datetime.datetime.utcnow()
    )
    db.add(owner_member)
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_CREATE",
        resource=f"team:{team.id}",
        details={"name": team.name, "color": team.color}
    )

    return TeamResponse(
        id=team.id,
        name=team.name,
        color=team.color,
        description=team.description,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=1,
        my_role="owner"
    )


@router.get("/{team_id}", response_model=TeamResponse)
def get_team_detail(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single team details."""
    team, role = get_team_and_role(team_id, current_user, db)
    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()

    return TeamResponse(
        id=team.id,
        name=team.name,
        color=team.color or "violet",
        description=team.description,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count,
        my_role=role
    )


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_in: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Edit team name, color badge, or description.
    Only team owner, team admin, or site-wide admin may edit.
    """
    team, role = get_team_and_role(team_id, current_user, db)

    if role not in ["owner", "admin"] and getattr(current_user, "role", "") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team owners and admins can edit team settings"
        )

    changes = {}
    if team_in.name is not None:
        new_name = team_in.name.strip()
        if not new_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Team name cannot be empty")
        # Check uniqueness per owner
        existing = db.query(Team).filter(
            Team.owner_id == team.owner_id,
            Team.name == new_name,
            Team.id != team.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A team named '{new_name}' already exists for this owner"
            )
        team.name = new_name
        changes["name"] = new_name

    if team_in.color is not None:
        team.color = team_in.color
        changes["color"] = team_in.color

    if team_in.description is not None:
        team.description = team_in.description
        changes["description"] = team_in.description

    team.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(team)

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_UPDATE",
        resource=f"team:{team.id}",
        details=changes
    )

    member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    return TeamResponse(
        id=team.id,
        name=team.name,
        color=team.color,
        description=team.description,
        owner_id=team.owner_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count,
        my_role=role
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    meetings: str = Query("move", pattern="^(move|delete)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete team: owner only (or site-wide admin).
    Requires 'meetings' parameter:
    - 'move': move team's meetings to owner's personal workspace (meeting.team_id = None)
    - 'delete': permanently delete them using perform_delete_meeting
    """
    team, role = get_team_and_role(team_id, current_user, db)

    is_site_admin = getattr(current_user, "role", "") == "admin"
    if role != "owner" and not is_site_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can delete the team"
        )

    # Fetch team members for notification before deleting
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    affected_user_ids = [m.user_id for m in members if m.user_id != current_user.id]

    team_name = team.name
    team_owner_id = team.owner_id

    # Handle meetings
    team_meetings = db.query(Meeting).filter(Meeting.team_id == team.id).all()
    if meetings == "move":
        for m in team_meetings:
            m.team_id = None
            # If the meeting owner was someone else, it still goes to owner workspace or stays with meeting owner
        db.commit()
    elif meetings == "delete":
        for m in team_meetings:
            try:
                perform_delete_meeting(m, db)
            except Exception as e:
                logger.error(f"Error deleting meeting {m.id} when deleting team {team_id}: {e}")

    # Remove invites and memberships
    db.query(TeamInvite).filter(TeamInvite.team_id == team.id).delete(synchronize_session=False)
    db.query(TeamMember).filter(TeamMember.team_id == team.id).delete(synchronize_session=False)

    # Delete team
    db.delete(team)
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_DELETE",
        resource=f"team:{team_id}",
        details={"name": team_name, "meetings_action": meetings, "affected_members": len(affected_user_ids)},
        severity="WARNING"
    )

    # Notify affected users
    for uid in affected_user_ids:
        create_user_notification(
            db=db,
            user_id=uid,
            title="Team Deleted",
            message=f"The team '{team_name}' has been deleted by {current_user.full_name or current_user.email}."
        )

    return None


# ==============================================================================
# Members Endpoints
# ==============================================================================

@router.get("/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all members of the team."""
    team, _ = get_team_and_role(team_id, current_user, db)

    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append(TeamMemberResponse(
            id=m.id,
            team_id=m.team_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            user_email=user.email if user else None,
            user_name=user.full_name if user else None,
            user_avatar=user.avatar_url if user else None,
        ))
    return result


@router.patch("/{team_id}/members/{user_id}", response_model=TeamMemberResponse)
def update_member_role(
    team_id: int,
    user_id: int,
    role_in: TeamMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change role of a member (admin, member, viewer).
    Rules:
    - Admins cannot change owner or other admins unless they are owner (or site-wide admin).
    - Nobody can demote or remove the last owner via this endpoint.
    """
    team, current_role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if current_role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    target_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in team")

    # Protection: Cannot change owner role directly (must transfer ownership)
    if target_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role of the team owner. Transfer ownership instead."
        )

    # Admin restriction: Admin cannot change another admin or owner unless current_user is owner or site admin
    if current_role == "admin" and not is_site_admin:
        if target_member.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot change the role of other admins"
            )

    old_role = target_member.role
    target_member.role = role_in.role
    db.commit()
    db.refresh(target_member)

    log_team_audit(
        db=db,
        user=current_user,
        action="MEMBER_ROLE_CHANGE",
        resource=f"team:{team_id}/member:{user_id}",
        details={"old_role": old_role, "new_role": role_in.role}
    )

    create_user_notification(
        db=db,
        user_id=user_id,
        title="Team Role Updated",
        message=f"Your role in team '{team.name}' has been updated to {role_in.role}."
    )

    user = db.query(User).filter(User.id == user_id).first()
    return TeamMemberResponse(
        id=target_member.id,
        team_id=target_member.team_id,
        user_id=target_member.user_id,
        role=target_member.role,
        joined_at=target_member.joined_at,
        user_email=user.email if user else None,
        user_name=user.full_name if user else None,
        user_avatar=user.avatar_url if user else None,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a member from the team.
    Rules:
    - Admins cannot remove owner or other admins unless they are owner (or site admin).
    - Cannot remove the last owner.
    """
    team, current_role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if current_role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    target_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    ).first()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in team")

    if target_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team owner. Transfer ownership first."
        )

    # Admin restriction: Admin cannot remove another admin unless current_user is owner or site admin
    if current_role == "admin" and not is_site_admin:
        if target_member.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot remove other admins"
            )

    db.delete(target_member)
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="MEMBER_REMOVE",
        resource=f"team:{team_id}/member:{user_id}",
        details={"removed_user_id": user_id}
    )

    create_user_notification(
        db=db,
        user_id=user_id,
        title="Removed from Team",
        message=f"You have been removed from team '{team.name}'."
    )

    return None


@router.post("/{team_id}/leave", status_code=status.HTTP_200_OK)
def leave_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Any member can leave the team except the sole owner.
    Leaver's meetings remain with the team.
    """
    team, role = get_team_and_role(team_id, current_user, db)

    if role == "owner":
        # Check if there are other owners (by rule each team has exactly one owner)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The team owner cannot leave the team. Transfer ownership before leaving."
        )

    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in team")

    db.delete(member)
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_LEAVE",
        resource=f"team:{team_id}",
        details={"user_id": current_user.id}
    )

    return {"message": f"Successfully left team '{team.name}'"}


@router.post("/{team_id}/transfer-ownership", status_code=status.HTTP_200_OK)
def transfer_team_ownership(
    team_id: int,
    req: TeamTransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transfer ownership to an existing member.
    The current owner becomes an admin.
    """
    team, role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if role != "owner" and not is_site_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can transfer ownership"
        )

    if req.new_owner_user_id == team.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already the team owner"
        )

    target_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == req.new_owner_user_id
    ).first()
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user is not a member of this team"
        )

    old_owner_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == team.owner_id
    ).first()

    # Old owner becomes admin
    if old_owner_member:
        old_owner_member.role = "admin"

    # New member becomes owner
    target_member.role = "owner"
    team.owner_id = req.new_owner_user_id
    team.updated_at = datetime.datetime.utcnow()

    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="OWNERSHIP_TRANSFER",
        resource=f"team:{team_id}",
        details={"previous_owner": current_user.id, "new_owner": req.new_owner_user_id},
        severity="WARNING"
    )

    create_user_notification(
        db=db,
        user_id=req.new_owner_user_id,
        title="Team Ownership Transferred",
        message=f"You are now the owner of team '{team.name}'."
    )

    return {"message": "Ownership successfully transferred"}


# ==============================================================================
# Invites Endpoints
# ==============================================================================

@router.post("/{team_id}/invites", response_model=TeamInviteResponse, status_code=status.HTTP_201_CREATED)
def create_team_invite(
    team_id: int,
    invite_in: TeamInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send an invite to an email address.
    Owner or admin only.
    Rate limited: max 15 invites per team in the last 10 minutes.
    Does NOT reveal whether an email has an existing account.
    """
    team, role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can invite members"
        )

    # Rate limiting: max 15 invites in last 10 mins
    ten_mins_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    recent_count = db.query(TeamInvite).filter(
        TeamInvite.team_id == team_id,
        TeamInvite.created_at >= ten_mins_ago
    ).count()
    if recent_count >= 15:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Invite rate limit exceeded. Please wait a few minutes before sending more invites."
        )

    clean_email = invite_in.email.strip().lower()

    # Revoke any prior pending invites for the same email in this team
    prior_invites = db.query(TeamInvite).filter(
        TeamInvite.team_id == team_id,
        TeamInvite.email == clean_email,
        TeamInvite.accepted_at.is_(None),
        TeamInvite.revoked_at.is_(None)
    ).all()
    for pi in prior_invites:
        pi.revoked_at = datetime.datetime.utcnow()

    token = secrets.token_urlsafe(32)
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(days=7)

    invite = TeamInvite(
        team_id=team_id,
        email=clean_email,
        role=invite_in.role,
        token=token,
        invited_by_id=current_user.id,
        created_at=now,
        expires_at=expires_at
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_INVITE_CREATE",
        resource=f"team:{team_id}/invite:{invite.id}",
        details={"email": clean_email, "role": invite_in.role}
    )

    return TeamInviteResponse(
        id=invite.id,
        team_id=invite.team_id,
        email=invite.email,
        role=invite.role,
        invited_by_id=invite.invited_by_id,
        invited_by_name=current_user.full_name or current_user.email,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        status="pending",
        invite_link=f"/join-team?token={invite.token}"
    )


@router.get("/{team_id}/invites", response_model=List[TeamInviteResponse])
def list_team_invites(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List pending invites for the team. Owner or admin only."""
    team, role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can view invites"
        )

    invites = db.query(TeamInvite).filter(
        TeamInvite.team_id == team_id,
        TeamInvite.accepted_at.is_(None),
        TeamInvite.revoked_at.is_(None)
    ).order_by(TeamInvite.created_at.desc()).all()

    now = datetime.datetime.utcnow()
    res = []
    for inv in invites:
        inv_status = "expired" if inv.expires_at < now else "pending"
        res.append(TeamInviteResponse(
            id=inv.id,
            team_id=inv.team_id,
            email=inv.email,
            role=inv.role,
            invited_by_id=inv.invited_by_id,
            invited_by_name=inv.invited_by.full_name if inv.invited_by else None,
            created_at=inv.created_at,
            expires_at=inv.expires_at,
            status=inv_status,
            invite_link=f"/join-team?token={inv.token}"
        ))
    return res


@router.post("/{team_id}/invites/{invite_id}/resend", response_model=TeamInviteResponse)
def resend_team_invite(
    team_id: int,
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resend invite: refreshes expiry date to 7 days from now."""
    team, role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    invite = db.query(TeamInvite).filter(
        TeamInvite.id == invite_id,
        TeamInvite.team_id == team_id
    ).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    invite.token = secrets.token_urlsafe(32)
    invite.expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    invite.revoked_at = None
    db.commit()
    db.refresh(invite)

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_INVITE_RESEND",
        resource=f"team:{team_id}/invite:{invite.id}",
        details={"email": invite.email}
    )

    return TeamInviteResponse(
        id=invite.id,
        team_id=invite.team_id,
        email=invite.email,
        role=invite.role,
        invited_by_id=invite.invited_by_id,
        invited_by_name=current_user.full_name or current_user.email,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        status="pending",
        invite_link=f"/join-team?token={invite.token}"
    )


@router.delete("/{team_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_team_invite(
    team_id: int,
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke a pending invite."""
    team, role = get_team_and_role(team_id, current_user, db)
    is_site_admin = getattr(current_user, "role", "") == "admin"

    if role not in ["owner", "admin"] and not is_site_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    invite = db.query(TeamInvite).filter(
        TeamInvite.id == invite_id,
        TeamInvite.team_id == team_id
    ).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    invite.revoked_at = datetime.datetime.utcnow()
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_INVITE_REVOKE",
        resource=f"team:{team_id}/invite:{invite.id}",
        details={"email": invite.email}
    )

    return None


@router.post("/invites/accept")
def accept_team_invite(
    token: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accept an invitation token to join a team.
    Validates single-use, non-expired, non-revoked.
    """
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation token")

    if invite.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has been revoked")

    if invite.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been used")

    if invite.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has expired")

    team = db.query(Team).filter(Team.id == invite.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team no longer exists")

    # Add user to team_members if not already member
    existing_member = db.query(TeamMember).filter(
        TeamMember.team_id == invite.team_id,
        TeamMember.user_id == current_user.id
    ).first()

    if not existing_member:
        member = TeamMember(
            team_id=invite.team_id,
            user_id=current_user.id,
            role=invite.role,
            joined_at=datetime.datetime.utcnow()
        )
        db.add(member)

    invite.accepted_at = datetime.datetime.utcnow()
    db.commit()

    log_team_audit(
        db=db,
        user=current_user,
        action="TEAM_INVITE_ACCEPT",
        resource=f"team:{team.id}",
        details={"email": current_user.email, "role": invite.role}
    )

    create_user_notification(
        db=db,
        user_id=team.owner_id,
        title="New Team Member",
        message=f"{current_user.full_name or current_user.email} joined team '{team.name}'."
    )

    return {
        "success": True,
        "message": f"Successfully joined team '{team.name}'",
        "team_id": team.id,
        "role": invite.role
    }


# ==============================================================================
# Notifications Endpoints
# ==============================================================================

@notifications_router.get("", response_model=List[NotificationResponse])
def get_user_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all notifications for the current user."""
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return notifs


@notifications_router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notif.read = True
    db.commit()
    return {"status": "ok"}


@notifications_router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read for current user."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == False
    ).update({"read": True}, synchronize_session=False)
    db.commit()
    return {"status": "ok"}
