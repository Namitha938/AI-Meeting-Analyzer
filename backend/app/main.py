import logging

from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager



from app.config import settings

from app.database import engine, Base, SessionLocal, ensure_db_schema

from app.models import User, Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics

from app.auth import get_password_hash

from app.routers.auth import router as auth_router

from app.routers.meetings import router as meetings_router

from app.routers.action_items import router as action_items_router

from app.routers.search import router as search_router

from app.routers.export import router as export_router

from app.routers.calendar import router as calendar_router

from app.routers.admin import router as admin_router

from app.routers.integrations import router as integrations_router

from app.routers.compliance import router as compliance_router

from app.routers.teams import router as teams_router, notifications_router

from app.routers.livekit_webhooks import router as livekit_webhooks_router

from app.routers.meeting_bot import router as meeting_bot_router



logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("meetora")



def seed_initial_demo_data():

    """Seeds sample data so frontend and swagger tests work out-of-the-box."""

    db = SessionLocal()

    try:

        # Check if users already exist

        if db.query(User).count() == 0:

            logger.info("Seeding initial demo user: jordan@meetora.ai / password123")

            demo_user = User(

                email="jordan@meetora.ai",

                hashed_password=get_password_hash("password123"),

                full_name="Jordan Davis",

                role="admin",

                is_active=True,

            )

            db.add(demo_user)

            db.commit()

            db.refresh(demo_user)



            # Seed demo meetings

            sample_meetings = [

                {

                    "title": "Weekly product sync",

                    "duration": 2538,

                    "color": "violet",

                    "tags": ["Product", "Q3", "Planning"],

                    "participants": ["Sarah Kim", "Marcus Lee", "Jordan Davis", "+4 others"],

                },

                {

                    "title": "Customer discovery — Acme",

                    "duration": 3360,

                    "color": "blue",

                    "tags": ["Research", "Enterprise"],

                    "participants": ["Jamie Miller", "Alex Lin", "+2 others"],

                },

                {

                    "title": "Q3 marketing planning",

                    "duration": 4320,

                    "color": "orange",

                    "tags": ["Marketing", "GTM"],

                    "participants": ["Devin Kane", "Rachel Scott", "+6 others"],

                },

                {

                    "title": "Design critique & handoff",

                    "duration": 2280,

                    "color": "pink",

                    "tags": ["Design", "Figma"],

                    "participants": ["Sarah Kim", "Noah Price", "+3 others"],

                },

            ]



            for idx, sm in enumerate(sample_meetings):

                m = Meeting(

                    title=sm["title"],

                    user_id=demo_user.id,

                    duration_seconds=sm["duration"],

                    status="completed",

                    participants=sm["participants"],

                    tags=sm["tags"],

                    color=sm["color"],

                )

                db.add(m)

                db.commit()

                db.refresh(m)



                # Add summary

                s = Summary(

                    meeting_id=m.id,

                    overview="Team aligned on timeline milestones and prioritized mobile onboarding flows for beta rollout.",

                    key_takeaways=[

                        "Design handoff is scheduled for Friday.",

                        "Engineering will begin implementation next Monday.",

                        "Beta release target confirmed for August 12.",

                    ],

                    next_steps="Finalize Figma tokens and test API integration endpoints.",

                )

                db.add(s)



                # Add action items

                actions = [

                    ("Finalize onboarding flows", "Sarah Kim", "Friday", "completed" if idx == 0 else "pending", "high"),

                    ("Share API documentation", "Marcus Lee", "Monday", "pending", "high"),

                    ("Schedule beta customer interviews", "Jamie Miller", "Aug 2", "pending", "medium"),

                ]

                for title, assignee, deadline, stat, prio in actions:

                    ai = ActionItem(

                        meeting_id=m.id,

                        title=title,

                        assignee=assignee,

                        deadline=deadline,

                        status=stat,

                        priority=prio,

                    )

                    db.add(ai)



                # Add decisions

                db.add(Decision(

                    meeting_id=m.id,

                    decision_text="Prioritize mobile responsive flows before desktop release",

                    category="Product Strategy",

                    rationale="Customer discovery interviews indicated 60% of executive reviews happen on tablet/mobile.",

                ))



                # Add transcripts

                db.add(Transcript(

                    meeting_id=m.id,

                    speaker="Sarah Kim",

                    start_time=0.0,

                    end_time=12.5,

                    text="Let's make sure the onboarding flow is ready for the beta group by Friday.",

                    is_action_item=True,

                ))

                db.add(Transcript(

                    meeting_id=m.id,

                    speaker="Marcus Lee",

                    start_time=13.0,

                    end_time=29.0,

                    text="I can own the API documentation and share the final version by Monday.",

                    is_action_item=True,

                ))



                # Add analytics

                db.add(MeetingAnalytics(

                    meeting_id=m.id,

                    sentiment_score=0.85,

                    talk_to_listen_ratio=1.1,

                    total_topics=3,

                    speaking_time_distribution={"Sarah Kim": 45, "Marcus Lee": 35, "Jordan Davis": 20},

                ))



                # Compute effectiveness dynamically

                try:

                    from app.ml.effectiveness import compute_effectiveness

                    demo_segs = [

                        {"speaker": "Sarah Kim", "start_time": 0.0, "end_time": 12.5, "text": "Let's make sure the onboarding flow is ready for the beta group by Friday."},

                        {"speaker": "Marcus Lee", "start_time": 13.0, "end_time": 29.0, "text": "I can own the API documentation and share the final version by Monday."}

                    ]

                    demo_acts = [

                        {"assignee": a[1], "due_date": a[2]} for a in actions

                    ]

                    eff_res = compute_effectiveness(

                        segments=demo_segs,

                        action_items=demo_acts,

                        agenda_text=sm["title"],

                    )

                    if eff_res:

                        m.effectiveness_score = eff_res["score"]

                        m.effectiveness_pillars = eff_res["pillars"]

                except Exception as seed_eff_err:

                    logger.warning(f"Error computing seed effectiveness: {seed_eff_err}")



                db.commit()

            logger.info("Seeding completed successfully.")

    except Exception as e:

        logger.error(f"Error seeding data: {e}")

        db.rollback()

    finally:

        db.close()



import asyncio

from starlette.types import ASGIApp, Scope, Receive, Send



class CancellationHandlingMiddleware:

    def __init__(self, app: ASGIApp):

        self.app = app



    async def __call__(self, scope: Scope, receive: Receive, send: Send):

        try:

            await self.app(scope, receive, send)

        except (asyncio.CancelledError, KeyboardInterrupt):

            # Normal shutdown or client disconnected prematurely; suppress 500 ASGI crash

            if scope.get("type") == "http":

                logger.info("Request cancelled due to client disconnect or shutdown: %s %s", scope.get("method", ""), scope.get("path", ""))

            return



@asynccontextmanager

async def lifespan(app: FastAPI):

    # Create DB tables

    Base.metadata.create_all(bind=engine)

    ensure_db_schema()

    seed_initial_demo_data()

    from app.routers.meetings import is_livekit_configured
    if not is_livekit_configured():
        logger.warning("Live meetings are not configured: LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET is missing. Live meetings will return 503.")

    try:

        yield

    except (asyncio.CancelledError, KeyboardInterrupt):

        pass



app = FastAPI(

    title=settings.PROJECT_NAME,

    version=settings.VERSION,

    description="FastAPI backend for Meetora AI Meeting Analyzer — transcription, speaker separation, action items, summaries, and analytics.",

    lifespan=lifespan,

    docs_url="/docs",

    redoc_url="/redoc",

)



# Handle client disconnect / server shutdown cancellations gracefully

app.add_middleware(CancellationHandlingMiddleware)



# CORS

app.add_middleware(

    CORSMiddleware,

    allow_origins=settings.CORS_ORIGINS,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)






# Static file serving for uploaded avatars and recordings

import os

from fastapi.staticfiles import StaticFiles

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")



# Mount routers under /api and root aliases

app.include_router(auth_router, prefix=settings.API_PREFIX)

app.include_router(meetings_router, prefix=settings.API_PREFIX)

app.include_router(action_items_router, prefix=settings.API_PREFIX)

app.include_router(search_router, prefix=settings.API_PREFIX)

app.include_router(export_router, prefix=settings.API_PREFIX)

app.include_router(calendar_router, prefix=settings.API_PREFIX)

app.include_router(admin_router, prefix=settings.API_PREFIX)

app.include_router(integrations_router, prefix=settings.API_PREFIX)

app.include_router(compliance_router, prefix=settings.API_PREFIX)

app.include_router(teams_router, prefix=settings.API_PREFIX)

app.include_router(notifications_router, prefix=settings.API_PREFIX)

app.include_router(livekit_webhooks_router, prefix=settings.API_PREFIX)

app.include_router(meeting_bot_router, prefix=settings.API_PREFIX)



# Also mount routers directly at root so calls without /api work seamlessly

app.include_router(auth_router)

app.include_router(meetings_router)

app.include_router(action_items_router)

app.include_router(search_router)

app.include_router(export_router)

app.include_router(calendar_router)

app.include_router(admin_router)

app.include_router(integrations_router)

app.include_router(compliance_router)

app.include_router(teams_router)

app.include_router(notifications_router)

app.include_router(livekit_webhooks_router)

app.include_router(meeting_bot_router)



@app.get("/health", tags=["Health"])

@app.get("/", tags=["Health"])

def health_check():

    return {

        "status": "healthy",

        "app": settings.PROJECT_NAME,

        "version": settings.VERSION,

        "docs": "/docs",

    }

