import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("meetora.db")

db_url = settings.DATABASE_URL
connect_args = {}

from sqlalchemy import event

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(db_url, connect_args=connect_args)

if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
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
                if "effectiveness_score" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN effectiveness_score INTEGER"))
                if "effectiveness_pillars" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN effectiveness_pillars JSON"))
                if "is_live" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN is_live BOOLEAN DEFAULT 0"))
                if "room_name" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN room_name VARCHAR(100)"))
                if "live_status" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN live_status VARCHAR(50) DEFAULT 'scheduled'"))
                if "host_id" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN host_id INTEGER"))
                if "started_at" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN started_at DATETIME"))
                if "ended_at" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN ended_at DATETIME"))
                if "record_mode" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN record_mode VARCHAR(50) DEFAULT 'audio_video'"))
                if "source" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN source VARCHAR(50) DEFAULT 'upload'"))
                if "meeting_code" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN meeting_code VARCHAR(50)"))
                if "passcode_hash" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN passcode_hash VARCHAR(255)"))
                if "locked" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN locked BOOLEAN DEFAULT 0"))
                if "waiting_room_enabled" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN waiting_room_enabled BOOLEAN DEFAULT 0"))
                if "meeting_link" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN meeting_link VARCHAR(500)"))
                if "platform" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN platform VARCHAR(50)"))
                if "auto_join" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN auto_join BOOLEAN DEFAULT 1"))
                if "consent_confirmed" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN consent_confirmed BOOLEAN DEFAULT 0"))
                if "consent_confirmed_at" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN consent_confirmed_at DATETIME"))
                if "bot_provider" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN bot_provider VARCHAR(50) DEFAULT 'mock'"))
                if "bot_id" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN bot_id VARCHAR(100)"))
                if "bot_status" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN bot_status VARCHAR(50) DEFAULT 'not_requested'"))
                if "bot_error" not in existing_m_cols:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN bot_error TEXT"))
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
            if "live_participants" not in inspector.get_table_names():
                from .models import LiveParticipant
                LiveParticipant.__table__.create(conn, checkfirst=True)
                conn.commit()
            else:
                existing_lp_cols = {c["name"] for c in inspector.get_columns("live_participants")}
                if "role" not in existing_lp_cols:
                    conn.execute(text("ALTER TABLE live_participants ADD COLUMN role VARCHAR(20) DEFAULT 'participant'"))
                if "status" not in existing_lp_cols:
                    conn.execute(text("ALTER TABLE live_participants ADD COLUMN status VARCHAR(30) DEFAULT 'admitted'"))
                if "is_muted" not in existing_lp_cols:
                    conn.execute(text("ALTER TABLE live_participants ADD COLUMN is_muted BOOLEAN DEFAULT 0"))
                if "video_disabled" not in existing_lp_cols:
                    conn.execute(text("ALTER TABLE live_participants ADD COLUMN video_disabled BOOLEAN DEFAULT 0"))
                conn.commit()
            if "meeting_chats" not in inspector.get_table_names():
                from .models import MeetingChat
                MeetingChat.__table__.create(conn, checkfirst=True)
                conn.commit()
            if "action_items" in inspector.get_table_names():
                existing_ai_cols = {c["name"] for c in inspector.get_columns("action_items")}
                if "status" not in existing_ai_cols:
                    conn.execute(text("ALTER TABLE action_items ADD COLUMN status VARCHAR(50) DEFAULT 'confirmed'"))
                if "start_time_sec" not in existing_ai_cols:
                    conn.execute(text("ALTER TABLE action_items ADD COLUMN start_time_sec FLOAT"))
                if "source_segment_id" not in existing_ai_cols:
                    conn.execute(text("ALTER TABLE action_items ADD COLUMN source_segment_id INTEGER"))
                conn.commit()
            if "decisions" in inspector.get_table_names():
                existing_dec_cols = {c["name"] for c in inspector.get_columns("decisions")}
                if "start_time_sec" not in existing_dec_cols:
                    conn.execute(text("ALTER TABLE decisions ADD COLUMN start_time_sec FLOAT"))
                if "source_segment_id" not in existing_dec_cols:
                    conn.execute(text("ALTER TABLE decisions ADD COLUMN source_segment_id INTEGER"))
                conn.commit()
            if "recordings" not in inspector.get_table_names():
                from .models import Recording
                Recording.__table__.create(conn, checkfirst=True)
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
