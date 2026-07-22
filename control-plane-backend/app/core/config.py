import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Thay đổi thông tin user, password, db_name theo database Postgres của bạn
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/pam_gateway")
    
    # Cấu hình Pydantic mặc định dùng snake_case cho toàn hệ thống
    model_config = ConfigDict(
        alias_generator=lambda s: s, # Giữ nguyên snake_case từ backend ra frontend
        populate_by_name=True
    )

settings = Settings()
