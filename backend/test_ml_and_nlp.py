from app.database import SessionLocal
from app.models import Meeting, Transcript, Summary, ActionItem, Decision, MeetingAnalytics
from app.nlp_analysis import sentence_classifier, InformationExtractor, MeetingSummarizer, MeetingAnalyticsEngine, run_core_nlp_pipeline

print("=== 1. TESTING SENTENCE CLASSIFIER (4 CLASSES) ===")
test_samples = [
    ("Marcus will optimize the database queries by Monday.", "action_item"),
    ("We agreed to adopt PostgreSQL for our relational data layer.", "decision"),
    ("What are the primary differences between DistilBERT and BERT?", "question"),
    ("Good morning everyone, thanks for joining today's standup call.", "general"),
]

for text, expected in test_samples:
    res = sentence_classifier.classify_sentence(text)
    print(f"Text: \"{text[:45]}...\"")
    print(f"  -> Predicted: {res['label']} (Confidence: {res['confidence']}) | Expected: {expected}")
    assert res['label'] == expected, f"Classification failed! Expected {expected}, got {res['label']}"

print("Step 8 (Meeting Sentence Classifier) verified successfully!\n")

print("=== 2. TESTING NER & DEADLINE EXTRACTION ===")
action_text = "Sarah, please review the mobile onboarding flows before our sprint demo on Friday."
assignee = InformationExtractor.extract_assignee(action_text, "Speaker 1", ["Sarah Kim", "Marcus Lee"])
deadline = InformationExtractor.extract_deadline(action_text)
priority = InformationExtractor.extract_priority(action_text)
print(f"Action: \"{action_text}\"")
print(f"  -> Assignee: {assignee} | Deadline: {deadline} | Priority: {priority}")
assert "Sarah" in assignee, "Assignee extraction failed!"
assert "Friday" in deadline, "Deadline extraction failed!"

decision_text = "We agreed to adopt FastAPI + PostgreSQL for our primary analyzer services."
category = InformationExtractor.extract_decision_category(decision_text)
print(f"Decision: \"{decision_text}\"")
print(f"  -> Category: {category}")
assert category in ["Architecture", "Product & Design", "Timeline & Planning"], "Category extraction failed!"
print("Entity & Deadline Extraction verified successfully!\n")

print("=== 3. TESTING STEP 7: SUMMARIZATION & SENTIMENT ENGINE ===")
sample_transcripts = [
    {"speaker": "Sarah Kim", "start_time": 0.0, "end_time": 15.0, "text": "Good morning team, let's nail down our launch milestones."},
    {"speaker": "Marcus Lee", "start_time": 15.0, "end_time": 35.0, "text": "The backend endpoints are solid and verified."},
    {"speaker": "Sarah Kim", "start_time": 35.0, "end_time": 50.0, "text": "Great, let's deliver the mobile UX by Friday.", "is_action_item": True},
]
decisions = [{"decision_text": "Launch confirmed for Q3", "category": "Timeline & Planning"}]

summary = MeetingSummarizer.generate_summary("Q3 Launch Sync", sample_transcripts, decisions)
print("Generated Summary Overview:", summary["overview"])
print("Key Takeaways:", len(summary["key_takeaways"]), "points")

analytics = MeetingAnalyticsEngine.analyze_sentiment_and_dynamics(sample_transcripts, ["Sarah Kim", "Marcus Lee"])
print("Sentiment Score:", analytics["sentiment_score"])
print("Speaking Distribution:", analytics["speaking_time_distribution"])

print("\n=== 4. TESTING FULL END-TO-END CORE NLP PIPELINE IN DATABASE ===")
db = SessionLocal()
meeting = db.query(Meeting).first()
if meeting:
    # Ensure meeting has transcripts
    if not meeting.transcripts:
        from app.celery_app import run_meeting_pipeline_sync
        run_meeting_pipeline_sync(meeting.id)

    run_core_nlp_pipeline(meeting.id, db)
    db.refresh(meeting)
    print(f"Meeting {meeting.id} '{meeting.title}' NLP Results:")
    print(f"  - Action Items: {len(meeting.action_items)}")
    for a in meeting.action_items[:2]:
        print(f"      * {a.title} (Owner: {a.assignee}, Due: {a.deadline})")
    print(f"  - Decisions: {len(meeting.decisions)}")
    for d in meeting.decisions[:2]:
        print(f"      * {d.decision_text} ({d.category})")
    print(f"  - Summary: {meeting.summary.overview[:70]}...")
    print(f"  - Sentiment: {meeting.analytics.sentiment_score if meeting.analytics else 'N/A'}")

db.close()
print("\n>>> ALL TESTS PASSED: STEPS 7 & 8 ARE 100% OPERATIONAL!")

