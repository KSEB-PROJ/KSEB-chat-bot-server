"""
챗봇 관련 API 라우팅을 처리하는 모듈.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..schemas.chatbot_schema import ChatRequest, ChatResponse
from ..services.chatbot_service import run_agent
from ..core.security import get_current_user_id

router = APIRouter(prefix="/api/v1/chatbot", tags=["Chatbot"])

@router.post(
    "/channels/{channel_id}/query",
    response_model=ChatResponse,
    summary="AI 챗봇에게 질의",
    description="사용자의 질문(query)과 인증 토큰을 받아 AI 에이전트를 실행하고 답변을 반환합니다.",
)
async def handle_chat_query(
    channel_id: int,
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    http_request: Request = None,  # FastAPI의 Request 객체로 헤더 접근
):
    """
    사용자의 질문을 받아 AI 에이전트를 실행하고, 생성된 답변을 반환하는 API 엔드포인트.
    """
    try:
        # JWT 토큰을 Authorization 헤더에서 추출 (Bearer 포함)
        jwt_token = None
        if http_request is not None:
            jwt_token = http_request.headers.get("authorization")  # 보통 'Bearer ...'

        answer = await run_agent(
            query=request.query,
            user_id=user_id,
            channel_id=channel_id,
            jwt_token=jwt_token,  # 서비스에 넘김
        )
        return ChatResponse(answer=answer)
    except Exception as e:
        print(f"에이전트 실행 중 오류 발생: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI 에이전트 요청 처리 중 오류가 발생했습니다: {str(e)}"
        ) from e
