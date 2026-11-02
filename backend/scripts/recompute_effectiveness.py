"""
Script to recompute Meeting Effectiveness scores and quality pillars for all existing meetings in the database.
Usage:
    cd backend
    python scripts/recompute_effectiveness.py
"""

import sys
import os

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, ensure_db_schema
from app.models import Meeting
from app.ml.effectiveness import compute_effectiveness


def recompute_all_meetings():
    ensure_db_schema()
    db = SessionLocal()
    try:
        meetings = db.query(Meeting).all()
        print(f"Found {len(meetings)} meeting(s) to process.\n")
        updated_count = 0

        print(f"{'ID':<4} | {'Score':<6} | {'Clarity':<8} | {'Action':<8} | {'Engage':<8} | {'Align':<8} | Title")
        print("-" * 85)

        for m in meetings:
            segments = [
                {
                    "speaker": t.speaker,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "text": t.text,
                }
                for t in m.transcripts
            ]
            action_items = [
                {
                    "assignee": a.assignee,
                    "due_date": a.deadline or getattr(a, "due_date", None),
                }
                for a in m.action_items
            ]

            eff = compute_effectiveness(
                segments=segments,
                action_items=action_items,
                agenda_text=m.description or m.title,
            )

            if eff:
                m.effectiveness_score = eff["score"]
                m.effectiveness_pillars = eff["pillars"]
                updated_count += 1
                p = eff["pillars"]
                print(f"{m.id:<4} | {eff['score']:<6} | {p['clarity']:<8} | {p['actionability']:<8} | {p['engagement']:<8} | {p['goal_alignment']:<8} | {m.title}")
            else:
                m.effectiveness_score = None
                m.effectiveness_pillars = None
                print(f"{m.id:<4} | {'--':<6} | {'--':<8} | {'--':<8} | {'--':<8} | {'--':<8} | {m.title} (no transcripts)")

        db.commit()
        print(f"\nSuccessfully updated effectiveness scores for {updated_count} meeting(s).")
    except Exception as e:
        db.rollback()
        print(f"Error recomputing effectiveness: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    recompute_all_meetings()

