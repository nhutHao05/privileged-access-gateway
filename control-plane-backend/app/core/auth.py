import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.models.auth_rbac import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token",
    auto_error=False
)

# Cache JWKS public keys để tránh gọi API liên tục
_jwks_cache = None

async def get_keycloak_public_keys():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    
    certs_url = f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(certs_url, timeout=5.0)
            if resp.status_code == 200:
                _jwks_cache = resp.json()
                return _jwks_cache
    except Exception as e:
        print(f"⚠️ [AUTH] Không thể lấy Public Key từ Keycloak ({certs_url}): {e}")
    return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency lấy thông tin User hiện tại từ JWT Bearer Token của Keycloak.
    Nếu không truyền Token (hoặc khi dev/test), hỗ trợ fallback lấy user đầu tiên trong DB.
    """
    if not token:
        # Fallback cho dev/test khi chưa gửi Bearer token trên Swagger UI
        user = db.query(User).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chưa truyền Bearer Token và chưa có User nào trong DB để test."
            )
        return user

    try:
        # Decode không verify signature nếu Keycloak chưa sẵn sàng certs, hoặc verify nếu có JWKS
        jwks = await get_keycloak_public_keys()
        payload = None
        
        if jwks:
            try:
                # Lấy key id từ header của token
                unverified_header = jwt.get_unverified_header(token)
                kid = unverified_header.get("kid")
                key = None
                for k in jwks.get("keys", []):
                    if k.get("kid") == kid:
                        key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                        break
                if key:
                    payload = jwt.decode(
                        token,
                        key=key,
                        algorithms=["RS256"],
                        options={"verify_aud": False}
                    )
            except Exception as ex:
                print(f"⚠️ [AUTH] Verify signature thất bại, fallback sang decode payload: {ex}")
        
        if not payload:
            payload = jwt.decode(token, options={"verify_signature": False})

        keycloak_sub = payload.get("sub")
        username = payload.get("preferred_username") or payload.get("username") or "unknown"
        email = payload.get("email")
        full_name = payload.get("name") or f"{payload.get('given_name', '')} {payload.get('family_name', '')}".strip()

        if not keycloak_sub:
            raise HTTPException(status_code=401, detail="Token không hợp lệ (thiếu sub).")

        sub_uuid = UUID(keycloak_sub)
        
        # Tìm User theo keycloak_sub hoặc username
        user = db.query(User).filter(
            (User.keycloak_sub == sub_uuid) | (User.username == username)
        ).first()

        # Nếu user chưa có trong DB -> Tự động sync từ Keycloak sang
        if not user:
            user = User(
                id=uuid.uuid4(),
                keycloak_sub=sub_uuid,
                username=username,
                email=email,
                full_name=full_name,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"🟢 [AUTH-SYNC] Đã tự động tạo User '{username}' từ Keycloak token!")
        else:
            # Cập nhật keycloak_sub nếu chưa có
            if not user.keycloak_sub:
                user.keycloak_sub = sub_uuid
                db.commit()

        return user

    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token Keycloak không hợp lệ: {str(e)}"
        )
