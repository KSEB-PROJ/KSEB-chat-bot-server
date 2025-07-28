"""
보안 관련 유틸리티 모듈.
"""
import json
from datetime import datetime
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from .config import settings

security_scheme = HTTPBearer()
ALGORITHM = settings.JWT_ALGORITHM

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> int:
    token = credentials.credentials
    try:
        secret_for_test = "ThisIsTheFinalTestSecretKeyPleaseWorkNow123"
        payload = jwt.decode(token, secret_for_test, algorithms=[ALGORITHM])
        
        # ★★★ 이 부분이 터미널에 로그를 출력합니다 ★★★
        print("--- DECODED JWT PAYLOAD ---")
        print(json.dumps(payload, indent=2))
        print("---------------------------")
        
        user_id = payload.get("userId") or payload.get("id") or payload.get("sub")
        exp = payload.get("exp")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: user_id not found")

        if exp is None or datetime.fromtimestamp(exp) < datetime.now():
            raise HTTPException(status_code=401, detail="Token has expired or invalid")

        return int(user_id)
        
    except JWTError as exc:
        # ★★★ 또는 여기서 에러 로그를 출력합니다 ★★★
        print(f"!!! JWT DECODE ERROR: {exc}")
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    