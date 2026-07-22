from fastapi import FastAPI
from app.core.config import settings
from app.routers import server, user_group, policy, access # Import router vừa tạo

app = FastAPI(title="PAM Gateway - RBAC Engine", version="0.1")
app.include_router(server.router)
app.include_router(user_group.router)
app.include_router(policy.router)
app.include_router(access.router)

@app.get("/")
def read_root():
    return {"status": "PAM Gateway Backend is running", "format": "snake_case_active"}