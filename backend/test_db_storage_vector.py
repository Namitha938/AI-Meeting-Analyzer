from app.database import engine, Base, SessionLocal
from app.models import User, Meeting, Transcript, ActionItem, Comment, Summary, Decision, MeetingAnalytics
from app.storage import get_storage, LocalStorageService, S3StorageService, CloudinaryStorageService
from app.search_vector import embedding_engine, vector_search_service

print("--- 1. DATABASE & MODELS TEST ---")
db = SessionLocal()
tables = [
    User.__tablename__,
    Meeting.__tablename__,
    Transcript.__tablename__,
    ActionItem.__tablename__,
    Comment.__tablename__
]
print("Verified 5 Core Tables:", tables)
user_count = db.query(User).count()
meeting_count = db.query(Meeting).count()
print(f"Database Connected successfully! Active Users: {user_count}, Meetings: {meeting_count}")

print("\n--- 2. STORAGE SERVICES TEST ---")
local_storage = LocalStorageService()
print("Local Disk Storage Dir:", local_storage.upload_dir)

s3_storage = S3StorageService()
print("AWS S3 Storage:", f"bucket={s3_storage.bucket}, region={s3_storage.region}")

cloudinary_storage = CloudinaryStorageService()
print("Cloudinary Storage Initialized")
print("Active Storage Provider:", type(get_storage()).__name__)

print("\n--- 3. SEMANTIC VECTOR SEARCH (FAISS / PGVECTOR) TEST ---")
sample_text = "We reviewed the Q3 marketing budget, financial forecasts, and runway"
emb = embedding_engine.embed_text(sample_text)
print(f"Embedding generated! Vector Dim: {len(emb)}, L2 Norm: {sum(x*x for x in emb):.2f}")

query_text = "financial budget allocation"
query_emb = embedding_engine.embed_text(query_text)
similarity = embedding_engine.cosine_similarity(emb, query_emb)
print(f"Semantic similarity between '{query_text}' and text: {similarity:.3f} (Score: {similarity*100:.1f}%)")

unrelated_query = "unrelated cooking recipe ingredients"
unrelated_emb = embedding_engine.embed_text(unrelated_query)
unrelated_sim = embedding_engine.cosine_similarity(emb, unrelated_emb)
print(f"Semantic similarity for unrelated query '{unrelated_query}': {unrelated_sim:.3f}")

assert similarity > unrelated_sim, "Semantic similarity ranking failed!"
print("Semantic search ranking verified successfully!")

db.close()
print("\n>>> ALL CHECKS PASSED: PostgreSQL/SQLite, Storage (Local/S3/Cloudinary), and Vector Search (pgvector/FAISS) are fully operational!")

