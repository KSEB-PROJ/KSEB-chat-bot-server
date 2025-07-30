# src/utils/api_client.py
from datetime import datetime
import httpx
from src.core.config import settings

# HTTP 클라이언트는 재사용하는 것이 효율적이므로 모듈 수준에서 정의.
client = httpx.AsyncClient(base_url=settings.MAIN_SERVER_URL)

async def fetch_messages_from_backend(channel_id: int, user_id: int, jwt_token: str) -> str:
    """메인 서버 API를 호출하여 채널의 전체 대화 내역을 가져옴."""
    if not jwt_token:
        return "인증 토큰이 없어 대화 내용을 가져올 수 없습니다."
        
    api_url = f"/api/channels/{channel_id}/chats"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "X-User-ID": str(user_id)
    }
    try:
        response = await client.get(api_url, headers=headers, timeout=10.0)
        response.raise_for_status()
        messages = response.json().get("data", [])
        if not messages:
            return "채널에 대화 내용이 없습니다."
        return "\n".join(
            f"[{datetime.fromisoformat(msg['createdAt']).strftime('%Y-%m-%d %H:%M')}] "
            f"{msg['userName']}: {msg.get('content') or '(파일)'}"
            for msg in messages
        )
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("message", "알 수 없는 오류")
        print(f"[API Client Error] 메인 서버 API 오류: {e.response.status_code} - {error_detail}")
        return f"대화 내용을 가져오는 데 실패했습니다: {error_detail}"
    except httpx.RequestError as e:
        print(f"[API Client Error] 메시지 조회 중 통신 오류 발생: {e}")
        return "대화 내용을 가져오는 중 서버와 통신할 수 없습니다."
