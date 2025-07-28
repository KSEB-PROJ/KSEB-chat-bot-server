"""
보안 관련 유틸리티 모듈.
"""
from datetime import datetime
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from .config import settings

# JWT 인증 스킴과 알고리즘 설정 (Spring 서버와 반드시 일치!)
security_scheme = HTTPBearer()
ALGORITHM = settings.JWT_ALGORITHM  # .env에서 불러온 값 사용(예: "HS256")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> int:
    """
    Authorization 헤더의 JWT를 검증하고 user_id 반환

    Spring Boot 서버에서 발급한 JWT는 payload에 "userId"로 user 정보를 저장하므로,
    "userId", "id", "sub" 중 하나라도 있으면 user_id로 사용하도록 함.
    """
    token = credentials.credentials
    try:
        # JWT 토큰을 검증(알고리즘과 시크릿은 Spring 서버와 반드시 일치!)
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        # 여러 필드명 중 하나라도 있으면 user_id로 인식
        user_id = payload.get("userId") or payload.get("id") or payload.get("sub")
        exp = payload.get("exp")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: user_id not found")
        if exp is None or datetime.fromtimestamp(exp) < datetime.now():
            raise HTTPException(status_code=401, detail="Token has expired or invalid")

        return int(user_id)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
