"""
챗봇 관련 API 라우팅을 처리하는 모듈.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from ..schemas.chatbot_schema import ChatRequest, ChatResponse
from ..services.chatbot_service import run_agent
from ..core.security import get_current_user_id

router = APIRouter(prefix="/api/v1/chatbot", tags=["Chatbot"])

@router.post(
    "/groups/{group_id}/channels/{channel_id}/query",
    response_model=ChatResponse,
    summary="AI 챗봇에게 질의",
    description="사용자의 질문(query)과 인증 토큰을 받아 AI 에이전트를 실행하고 답변을 반환합니다.",
)
async def handle_chat_query(
    group_id: int,
    channel_id: int,
    request: ChatRequest,
    http_request: Request,         # 반드시 Depends보다 앞에 위치!
    user_id: int = Depends(get_current_user_id),
):
    """
    사용자의 질문을 받아 AI 에이전트를 실행하고, 생성된 답변을 반환하는 API 엔드포인트.
    """
    try:
        # JWT 토큰을 Authorization 헤더에서 추출 ("Bearer ..."에서 Bearer 떼기)
        jwt_token = None
        if http_request is not None:
            raw_token = http_request.headers.get("authorization")
            if raw_token and raw_token.lower().startswith("bearer "):
                jwt_token = raw_token[7:]  # 'Bearer ' prefix 잘라냄
            else:
                jwt_token = raw_token

        answer = await run_agent(
            query=request.query,
            user_id=user_id,
            group_id=group_id,
            channel_id=channel_id,
            jwt_token=jwt_token,  # Bearer 없는 진짜 토큰만 서비스에 넘김
        )
        return ChatResponse(answer=answer)
    except Exception as e:
        print(f"에이전트 실행 중 오류 발생: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI 에이전트 요청 처리 중 오류가 발생했습니다: {str(e)}"
        ) from e
