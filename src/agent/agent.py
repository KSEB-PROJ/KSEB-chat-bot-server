"""
LangChain 에이전트를 래핑하는 모듈.
"""

from ksebj_chat_bot_server.services.schedule_service import agent_executor

async def chat_with_agent(text: str, user_id: int) -> str:
    """AgentExecutor에 질의를 전달하고 결과를 리턴."""
    result = await agent_executor.ainvoke({"input": text, "user_id": user_id})
    return result.get("output", "")
