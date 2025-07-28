"""
챗봇 관련 API 라우터 정의.
"""

from fastapi import APIRouter, Depends
from ksebj_chat_bot_server.schemas.chat import ChatRequest, ChatResponse
from ksebj_chat_bot_server.core.security import get_current_user_id

router = APIRouter()


@router.post("/query", response_model=ChatResponse)
async def handle_chatbot_query(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """사용자 query를 LangChain 에이전트에 전달하고 결과를 반환."""
    answer = await run_agent(req.query, user_id)
    return ChatResponse(answer=answer)
