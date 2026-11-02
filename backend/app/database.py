import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("meetora.db")

db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_db_schema():
    """Ensures newly added columns in SQLite are safely migrated without dropping existing tables."""
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "users" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("users")}
                if "voiceprint_enrolled" not in existing_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN voiceprint_enrolled BOOLEAN DEFAULT 0"))
                if "voiceprint_sample_path" not in existing_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN voiceprint_sample_path VARCHAR"))
                if "voiceprint_metrics" not in existing_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN voiceprint_metrics JSON"))
                conn.commit()
            if "human_corrections" in inspector.get_table_names():
                existing_hc_cols = {c["name"] for c in inspector.get_columns("human_corrections")}
                if "meeting_id" not in existing_hc_cols:
                    conn.execute(text("ALTER TABLE human_corrections ADD COLUMN meeting_id INTEGER"))
                conn.commit()
            if "meetings" in inspector.get_table_names():
                existing_m_cols = {c["name"] for c in inspector.get_columns("meetings")}
                if "description" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN description TEXT"))
                if "scheduled_at" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN scheduled_at DATETIME"))
                if "team_id" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN team_id INTEGER"))
                conn.commit()
            if "summaries" in inspector.get_table_names():
                existing_s_cols = {c["name"] for c in inspector.get_columns("summaries")}
                if "edited_by_user" not in existing_s_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN edited_by_user BOOLEAN DEFAULT 0"))
                if "updated_at" not in existing_s_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN updated_at DATETIME"))
                if "updated_by" not in existing_s_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN updated_by VARCHAR(100)"))
                conn.commit()
            if "meeting_shares" not in inspector.get_table_names():
                from .models import MeetingShare
                MeetingShare.__table__.create(conn, checkfirst=True)
                conn.commit()
            
            # Team management tables
            from .models import Team, TeamMember, TeamInvite, Notification
            table_names = inspector.get_table_names()
            if "teams" not in table_names:
                Team.__table__.create(conn, checkfirst=True)
            if "team_members" not in table_names:
                TeamMember.__table__.create(conn, checkfirst=True)
            if "team_invites" not in table_names:
                TeamInvite.__table__.create(conn, checkfirst=True)
            if "notifications" not in table_names:
                Notification.__table__.create(conn, checkfirst=True)
            conn.commit()

            # Migrate existing teams so their creator becomes owner in team_members
            conn.execute(text("""
                INSERT INTO team_members (team_id, user_id, role, joined_at)
                SELECT t.id, t.owner_id, 'owner', CURRENT_TIMESTAMP
                FROM teams t
                WHERE NOT EXISTS (
                    SELECT 1 FROM team_members tm WHERE tm.team_id = t.id AND tm.user_id = t.owner_id
                )
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"Auto-migration check notice: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
