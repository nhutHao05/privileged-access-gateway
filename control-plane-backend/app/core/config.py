import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/pam_gateway")
    
    # Guacamole API
    GUACAMOLE_BASE_URL: str = os.getenv("GUACAMOLE_BASE_URL", "http://100.77.136.104:8080/guacamole/api")
    GUACAMOLE_ADMIN_USER: str = os.getenv("GUACAMOLE_ADMIN_USER", "guacadmin")
    GUACAMOLE_ADMIN_PASS: str = os.getenv("GUACAMOLE_ADMIN_PASS", "guacadmin")
    
    # Keycloak OAuth2 / OIDC
    KEYCLOAK_SERVER_URL: str = os.getenv("KEYCLOAK_SERVER_URL", "http://100.77.136.104:8080")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "pam-realm")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "fastapi-backend")
    KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "98a1c5d3-8b4e-4f12-9c31-7e8b2a14d5f6")
    KEYCLOAK_OIDC_URL: str = os.getenv("KEYCLOAK_OIDC_URL", "http://100.77.136.104:8080/realms/pam-realm/.well-known/openid-configuration")
    
    # Cấu hình Pydantic mặc định dùng snake_case cho toàn hệ thống
    model_config = ConfigDict(
        alias_generator=lambda s: s, # Giữ nguyên snake_case từ backend ra frontend
        populate_by_name=True
    )

settings = Settings()
