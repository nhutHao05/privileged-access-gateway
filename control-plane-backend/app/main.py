from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.scheduler import scheduler
from app.routers import server, user_group, policy, access, audit

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    print("⏰ [SCHEDULER] APScheduler đã khởi động.")
    yield
    scheduler.shutdown()
    print("⏰ [SCHEDULER] APScheduler đã tắt.")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PAM Gateway - RBAC Engine", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(server.router)
app.include_router(user_group.router)
app.include_router(policy.router)
app.include_router(access.router)
app.include_router(audit.router)

# Serve static assets (CSS, JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Admin Control Plane — http://HOST:8000/ui
@app.get("/ui", include_in_schema=False)
def admin_dashboard():
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))

# User Self-Service Portal — http://HOST:8000/portal
@app.get("/portal", include_in_schema=False)
def user_portal():
    return FileResponse(str(BASE_DIR / "templates" / "portal.html"))

@app.get("/")
def read_root():
    return {
        "status": "PAM Gateway v2.0 is running",
        "admin_ui": "/ui",
        "user_portal": "/portal",
        "api_docs": "/docs"
    }