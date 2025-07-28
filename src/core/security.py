"""
보안 관련 헬퍼: JWT 토큰 검증 및 사용자 ID 추출.
"""

from datetime import datetime
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

# 절대 경로로 import
from .config import settings


security_scheme = HTTPBearer()
ALGORITHM = "HS512"


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> int:
    """Authorization 헤더의 JWT를 검증하고 user_id를 반환합니다."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        exp = payload.get("exp")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: user_id not found")
        if exp is None or datetime.fromtimestamp(exp) < datetime.now():
            raise HTTPException(status_code=401, detail="Token has expired or invalid")

        return int(user_id)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
