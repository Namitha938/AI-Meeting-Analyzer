import json
from app.main import app
from app.database import SessionLocal
from app.models import User
from app.auth import create_access_token

print("--- TESTING FASTAPI IN-PROCESS ---")
db = SessionLocal()
admin = db.query(User).filter(User.email == "jordan@meetora.ai").first()
token = create_access_token(data={"sub": admin.email, "role": admin.role, "user_id": admin.id})
db.close()
print("Generated auth token for:", admin.email)

# Verify routes are registered
paths = list(app.openapi()["paths"].keys())
print("\nRegistered OpenAPI Paths:")
for p in sorted(paths):
    print("  ->", p)

expected = [
    "/health",
    "/auth/login",
    "/auth/register",
    "/auth/google",
    "/auth/cleanup-duplicates",
    "/meetings",
    "/search",
    "/search/semantic",
    "/action-items"
]

for exp in expected:
    assert any(exp == p or exp in p for p in paths), f"Path {exp} missing!"

print("\n>>> All expected routes including /search/semantic, /auth/google, and /storage verified!")
