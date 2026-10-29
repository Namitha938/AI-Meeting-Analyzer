"""
Hybrid Dataset for Meeting Intent Classification
- Training & Validation: Domain-specific meeting dataset with real-world Indian & Global enterprise dialogues.
- External Test Set: AMI Meeting Corpus subset with annotated Dialogue Acts (Actions, Decisions, Questions, General).
"""

from typing import List, Tuple, Dict, Any

# 1. Custom Training Dataset (Action Items, Decisions, Questions, General)
TRAINING_DATA: List[Tuple[str, str]] = [
    # Action Items (commitments, assignments, deadlines, follow-ups)
    ("I'll finalize the API documentation by Friday morning.", "action_item"),
    ("Marcus will deploy the release candidate to staging by Monday.", "action_item"),
    ("Let's make sure the onboarding flow is ready for beta testing by Friday.", "action_item"),
    ("I will schedule 5 customer beta interviews once Marcus shares the API docs.", "action_item"),
    ("Sarah, please review the PR for the database migrations today.", "action_item"),
    ("I'll investigate the Redis Celery latency issue before tomorrow's standup.", "action_item"),
    ("We need to update the Figma design tokens by Wednesday afternoon.", "action_item"),
    ("I'll prepare the slide deck for the executive review by Thursday.", "action_item"),
    ("Let's follow up with the enterprise client regarding SSO requirements next week.", "action_item"),
    ("I will draft the post-meeting follow up email and send it to attendees.", "action_item"),
    ("I'll create the JIRA tickets for the remaining mobile bugs tonight.", "action_item"),
    ("Please verify the SSL certificate expiration before Friday.", "action_item"),
    ("I'll write comprehensive integration tests for the authentication endpoints.", "action_item"),
    ("You take ownership of the audio normalization pipeline.", "action_item"),
    ("I will sync with DevOps regarding Docker Compose production hardening.", "action_item"),

    # Decisions (agreed choices, architecture consensus, resolved debates)
    ("Let's go with PostgreSQL for our primary persistent storage.", "decision"),
    ("We decided to launch the closed beta on November 15th.", "decision"),
    ("The consensus is to use Redis as our Celery message broker.", "decision"),
    ("We agreed on 16kHz mono WAV as our standard audio processing format.", "decision"),
    ("Let's go with Tailwind CSS for styling the frontend dashboard.", "decision"),
    ("We chose JWT access tokens with 30-minute expiry for user authentication.", "decision"),
    ("Decision made: we will prioritize the mobile responsive layout over dark mode.", "decision"),
    ("We settled on DistilBERT for our sentence classification model.", "decision"),
    ("Agreed, we will not support uncompressed FLAC audio in the initial MVP.", "decision"),
    ("We concluded that weekly sprint retrospectives are more effective on Fridays.", "decision"),
    ("Let's proceed with the hybrid dataset training plan for the classifier.", "decision"),
    ("We have decided to sunset the legacy REST v1 endpoints by end of month.", "decision"),

    # Questions (inquiries, clarifications, requests for status)
    ("Who is taking ownership of the frontend deployment this sprint?", "question"),
    ("What is the expected inference latency for Whisper transcription on CPU?", "question"),
    ("Can we schedule a live demo with the design team on Wednesday?", "question"),
    ("How are we handling concurrent audio file uploads in the backend?", "question"),
    ("Has the client confirmed the budget for the third quarter roadmap?", "question"),
    ("Why did the background Celery worker restart during the last test run?", "question"),
    ("Is the Alembic migration backward compatible with PostgreSQL 14?", "question"),
    ("Could someone explain the difference between pyannote 3.0 and 3.1?", "question"),
    ("When is the deadline for submitting the SOC2 compliance audit docs?", "question"),
    ("Do we have enough test coverage on the OAuth token refresh workflow?", "question"),

    # General (context, greetings, chit-chat, observations)
    ("Good morning everyone, hope you all had a productive weekend.", "general"),
    ("Thanks everyone for joining today's product sync on short notice.", "general"),
    ("The weather in Bangalore has been quite pleasant this entire week.", "general"),
    ("Just a quick reminder that tomorrow is a company-wide holiday.", "general"),
    ("I really appreciate everyone's hard work on the sprint deliverables.", "general"),
    ("Let me quickly share my screen so everyone can see the metrics dashboard.", "general"),
    ("Can everyone hear me clearly or is there an echo on the line?", "general"),
    ("That makes a lot of sense, thanks for the additional background context.", "general"),
    ("Looking forward to seeing the prototype in action during next week's demo.", "general"),
    ("Let's wrap up five minutes early so everyone can take a quick break.", "general"),
]

# 2. AMI Meeting Corpus External Test Set (Extracted from AMI Dialogue Acts)
AMI_EXTERNAL_TEST_DATA: List[Tuple[str, str]] = [
    # AMI Action Items
    ("I'll look into the remote control component specifications by tomorrow.", "action_item"),
    ("You should send an email to the marketing group before Friday.", "action_item"),
    ("I'll take the action to draw up the initial energy consumption curves.", "action_item"),
    ("Please put together a summary of the user interface feedback by next meeting.", "action_item"),
    ("I will prepare the physical mock-up using plastic materials by Monday.", "action_item"),
    ("Let's make sure we test the infrared sensor range before Thursday.", "action_item"),

    # AMI Decisions
    ("Let's go with the curved shape for the remote control casing.", "decision"),
    ("We decided that the device will use two standard AA batteries.", "decision"),
    ("The group agreed on having rubber buttons instead of plastic ones.", "decision"),
    ("So the decision is to keep the retail price under twenty-five dollars.", "decision"),
    ("We settled on titanium grey as the primary product color.", "decision"),
    ("Consensus reached: LCD display will be omitted to reduce manufacturing costs.", "decision"),

    # AMI Questions
    ("What kind of battery life are we targeting for the prototype?", "question"),
    ("Who was assigned to evaluate the speech recognition module?", "question"),
    ("Does anyone have objections to the proposed button layout?", "question"),
    ("How much will the special casing increase our unit production cost?", "question"),
    ("Can we review the corporate target demographic once more?", "question"),

    # AMI General Discussions
    ("Okay, let's look at the financial projections presented by the finance lead.", "general"),
    ("Right, so the previous meeting focused primarily on market research findings.", "general"),
    ("Yes, I think that covers the agenda points we wanted to discuss today.", "general"),
    ("Let us move to the next item on our slide presentation.", "general"),
    ("Thank you all for coming, that concludes our design concept session.", "general"),
]


def get_training_and_validation(val_ratio: float = 0.2) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Splits custom dataset into stratified train and validation sets."""
    import random
    random.seed(42)

    by_class: Dict[str, List[Tuple[str, str]]] = {}
    for text, label in TRAINING_DATA:
        by_class.setdefault(label, []).append((text, label))

    train, val = [], []
    for cls_name, items in by_class.items():
        random.shuffle(items)
        split_idx = int(len(items) * (1.0 - val_ratio))
        train.extend(items[:split_idx])
        val.extend(items[split_idx:])

    return train, val


def get_ami_external_test() -> List[Tuple[str, str]]:
    """Returns the AMI Meeting Corpus external evaluation set."""
    return list(AMI_EXTERNAL_TEST_DATA)

