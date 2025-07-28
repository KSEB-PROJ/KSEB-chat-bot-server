"""
LangChain을 사용하여 AI 에이전트를 생성하고,
챗봇의 핵심 로직을 처리하는 서비스 모듈입니다.
"""
import httpx
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ksebj_chat_bot_server.core.config import settings

# HTTP 클라이언트를 재사용하기 위해 모듈 수준에서 정의합니다.
# settings.py에 정의된 SPRING_BOOT_BASE_URL을 기본 URL로 사용합니다.
client = httpx.AsyncClient(base_url=settings.SPRING_BOOT_BASE_URL)


@tool
async def create_schedule(title: str, start_time: str, end_time: str, user_id: int) -> str:
    """
    사용자의 요청에 따라 새로운 개인 일정을 생성합니다.
    - title: 일정의 제목
    - start_time: 시작 시간 (ISO 8601 형식, 예: '2025-07-28T14:00:00')
    - end_time: 종료 시간 (ISO 8601 형식, 예: '2025-07-28T15:00:00')
    - user_id: 현재 사용자의 ID
    """
    print(
        f"Executing create_schedule: {title}, {start_time}, {end_time}, user_id: {user_id}"
    )
    try:
        # Spring Boot API의 일정 생성 엔드포인트(/schedule)로 POST 요청을 보냅니다.
        # 요청 본문(JSON)에는 일정 정보를, 헤더에는 사용자 ID를 담아 보냅니다.
        response = await client.post(
            "/schedule",
            json={"title": title, "startTime": start_time, "endTime": end_time},
            headers={"X-User-ID": str(user_id)},
        )
        response.raise_for_status()  # 2xx 응답이 아니면 예외를 발생시킵니다.
        # 성공 시, Spring Boot에서 받은 응답 메시지를 반환합니다.
        return response.json().get("message", f"'{title}' 일정이 성공적으로 생성되었습니다.")
    except httpx.HTTPStatusError as e:
        # API 서버에서 오류 응답이 온 경우, 오류 메시지를 반환합니다.
        error_message = e.response.json().get("message", "알 수 없는 오류가 발생했습니다.")
        return f"일정 생성에 실패했습니다: {error_message}"
    except httpx.RequestError as e:
        # 네트워크 오류 등 요청 자체에 문제가 생긴 경우
        return f"서버 통신 중 오류가 발생했습니다: {e}"


@tool
async def get_schedule(date: str, user_id: int) -> str:
    """
    특정 날짜의 사용자 일정을 조회합니다.
    - date: 조회할 날짜 (YYYY-MM-DD 형식, 예: '2025-07-28')
    - user_id: 현재 사용자의 ID
    """
    print(f"Executing get_schedule: {date}, user_id: {user_id}")
    try:
        # Spring Boot API의 날짜별 일정 조회 엔드포인트(/schedule/{date})로 GET 요청을 보냅니다.
        response = await client.get(
            f"/schedule/{date}",
            headers={"X-User-ID": str(user_id)},
        )
        response.raise_for_status()
        schedules = response.json()
        if not schedules:
            return f"{date}에는 일정이 없습니다."

        # 조회된 일정 목록을 사람이 읽기 좋은 형태로 가공하여 반환합니다.
        schedule_list_str = "\n".join(
            [f"- {s['title']} ({s['startTime']} ~ {s['endTime']})" for s in schedules]
        )
        return f"{date}의 일정 목록입니다:\n{schedule_list_str}"
    except httpx.HTTPStatusError as e:
        error_message = e.response.json().get("message", "알 수 없는 오류가 발생했습니다.")
        return f"일정 조회에 실패했습니다: {error_message}"
    except httpx.RequestError as e:
        return f"서버 통신 중 오류가 발생했습니다: {e}"


llm = ChatOpenAI(model="gpt-4o")
tools = [create_schedule, get_schedule]

# 프롬프트에 user_id를 포함하여 에이전트가 도구를 호출할 때 이 값을 사용하도록 명시합니다.
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. "
            "When using tools, you must pass the user_id. "
            "The current user's ID is {user_id}.",
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


async def run_agent(query: str, user_id: int) -> str:
    """
    사용자 질문과 ID를 받아 AI 에이전트를 실행하고 답변을 반환합니다.
    """
    # 에이전트 실행 시 'user_id'를 함께 전달하여 프롬프트에 주입합니다.
    result = await agent_executor.ainvoke({"input": query, "user_id": user_id})
    return result.get("output", "죄송합니다. 답변을 생성하지 못했습니다.")
