from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.scheduler import scheduler
from app.routers import server, user_group, policy, access, audit

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: khởi động scheduler
    scheduler.start()
    print("⏰ [SCHEDULER] APScheduler đã khởi động.")
    yield
    # Shutdown: tắt scheduler sạch sẽ
    scheduler.shutdown()
    print("⏰ [SCHEDULER] APScheduler đã tắt.")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PAM Gateway - RBAC Engine", version="0.1", lifespan=lifespan)

# Cấu hình CORS để Frontend UI của Nghĩa gọi API không bị trình duyệt chặn
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

@app.get("/")
def read_root():
    return {"status": "PAM Gateway Backend is running", "format": "snake_case_active"}