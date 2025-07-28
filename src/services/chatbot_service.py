"""
LangChain을 사용하여 AI 에이전트를 생성하고,
챗봇의 핵심 로직을 처리하는 서비스 모듈.
"""
# 표준 라이브러리
from datetime import datetime

# 서드파티 라이브러리
import httpx
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# 로컬 애플리케이션 라이브러리
from src.core.config import settings

# HTTP 클라이언트는 재사용하는 것이 효율적이므로 모듈 수준에서 정의.
client = httpx.AsyncClient(base_url=settings.MAIN_SERVER_URL)

# ChatOpenAI를 생성할 때, 설정 파일에서 읽어온 API 키를 명시적으로 전달합니다.
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

# 오늘 날짜를 문자열로 저장 (프롬프트에 동적으로 사용)
today_str = datetime.now().strftime('%Y-%m-%d %A')


# --- 내부 헬퍼 함수 ---
async def fetch_messages_from_backend(channel_id: int, user_id: int, jwt_token: str) -> str:
    """[내부 함수] 메인 서버 API를 호출하여 채널의 전체 대화 내역을 가져옴."""
    api_url = f"/api/channels/{channel_id}/chats"
    headers = {
        "X-User-ID": str(user_id),
        "Authorization": jwt_token,
    }
    try:
        response = await client.get(api_url, headers=headers)
        response.raise_for_status()
        messages = response.json().get("data", [])
        if not messages:
            return ""
        # AI가 시간 필터링을 더 잘 할 수 있도록 날짜까지 포함하여 포맷팅
        return "\n".join(
            f"[{datetime.fromisoformat(msg['createdAt']).strftime('%Y-%m-%d %H:%M')}] "
            f"{msg['userName']}: {msg.get('content') or '(파일)'}"
            for msg in messages
        )
    except httpx.HTTPStatusError as e:
        print(f"메인 서버 API 오류: {e.response.status_code}")
        raise ValueError("대화 내용을 가져오는 데 실패했습니다.") from e
    except Exception as e:
        print(f"메시지 조회 중 알 수 없는 오류 발생: {e}")
        raise ValueError("대화 내용을 가져오는 중 문제가 발생했습니다.") from e


# --- LangChain 도구(Tools) 정의 ---
@tool
async def create_schedule(title: str, start_time: str, end_time: str, user_id: int, jwt_token: str) -> str:
    """새로운 개인 일정 생성. 사용자가 '일정 추가', '미팅 잡아줘' 등과 같이 말할 때 사용."""
    print(f"Executing create_schedule for user {user_id}: {title}")
    try:
        response = await client.post(
            "/api/users/me/events",
            json={
                "title": title,
                "startDatetime": start_time,
                "endDatetime": end_time,
                "allDay": False,
                "themeColor": "#3b82f6"
            },
            headers={
                "X-User-ID": str(user_id),
                "Authorization": jwt_token,
            },
        )
        response.raise_for_status()
        return response.json().get("message", f"'{title}' 일정이 성공적으로 생성되었습니다.")
    except httpx.HTTPStatusError as e:
        error_message = e.response.json().get("message", "알 수 없는 오류")
        return f"일정 생성 실패: {error_message}"
    except httpx.RequestError as e:
        return f"서버 통신 오류: {e}"


@tool
async def get_schedule(date: str, user_id: int, jwt_token: str) -> str:
    """특정 날짜의 사용자 일정을 조회. '오늘 일정 알려줘', '내일 스케줄' 등과 같이 말할 때 사용."""
    print(f"Executing get_schedule for user {user_id} on {date}")
    try:
        response = await client.get(
            "/api/users/me/events",
            headers={
                "X-User-ID": str(user_id),
                "Authorization": jwt_token,
            }
        )
        response.raise_for_status()
        schedules = response.json().get("data", [])

        target_date = datetime.strptime(date, "%Y-%m-%d").date()

        date_schedules = [
            s for s in schedules
            if datetime.fromisoformat(s['startDatetime']).date() == target_date
        ]

        if not date_schedules:
            return f"{date}에는 일정이 없습니다."

        schedule_list_str = "\n".join(
            [f"- {s['title']} ({datetime.fromisoformat(s['startDatetime']).strftime('%H:%M')} ~ {datetime.fromisoformat(s['endDatetime']).strftime('%H:%M')})" for s in date_schedules]
        )
        return f"{date}의 일정 목록입니다:\n{schedule_list_str}"
    except httpx.HTTPStatusError as e:
        error_message = e.response.json().get("message", "알 수 없는 오류")
        return f"일정 조회 실패: {error_message}"
    except httpx.RequestError as e:
        return f"서버 통신 오류: {e}"


@tool
async def summarize_channel_conversations(user_id: int, channel_id: int, jwt_token: str, time_query: str = "all") -> str:
    """
    채널의 대화 내용을 요약. '회의 요약해줘', '대화 정리해줘' 등과 같이 말할 때 사용.
    - user_id: 현재 사용자 ID (필수)
    - channel_id: 현재 보고 있는 채널의 ID (필수)
    - jwt_token: 현재 유저의 JWT 토큰(반드시 스프링 서버와 동기화된 토큰)
    - time_query: '오늘 오후 2시', '어제 회의' 와 같이 요약할 시간대를 나타내는 자연어. 사용자가 시간을 언급하지 않으면 'all'을 사용.
    """
    print(f"Executing summary for user {user_id} in channel {channel_id} with time_query: '{time_query}'")
    full_conversation = await fetch_messages_from_backend(channel_id, user_id, jwt_token)
    if not full_conversation:
        return "요약할 대화 내용이 없습니다."

    conversation_to_summarize = full_conversation
    # 사용자가 특정 시간을 요청한 경우, AI를 이용해 해당 부분만 필터링
    if time_query != "all":
        filtering_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                (
                    "당신은 대화 로그에서 시간 조건에 맞는 메시지만 정밀하게 추출하는 전문가입니다.\n"
                    f"오늘은 {today_str}입니다. 전체 대화 로그는 아래와 같고, 각 행은 '[YYYY-MM-DD HH:MM] 작성자: 내용' 형태입니다.\n"
                    "사용자가 요청한 시간 조건(time_query)에 맞는 대화만 뽑아서, 원문 그대로 반환하세요.\n"
                    "불필요한 해설, 추가 설명 없이 매칭되는 메시지만 리턴하세요.\n"
                    "만약 매칭되는 메시지가 없다면 'No Match'라고만 적어주세요."
                )
            ),
            (
                "human",
                "시간 조건: {time_query}\n\n전체 대화:\n---\n{conversation}\n---"
            ),
        ])
        filtering_chain = filtering_prompt | llm
        filtered_result = await filtering_chain.ainvoke({
            "time_query": time_query,
            "conversation": full_conversation
        })
        conversation_to_summarize = getattr(filtered_result, "content", "")
        if not conversation_to_summarize.strip() or "No Match" in conversation_to_summarize:
            return f"'{time_query}'에 해당하는 대화를 찾지 못했습니다."

    summarize_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "아래는 대학생 협업툴의 채팅/회의 대화입니다.\n"
                "주요 주제, 논의 내용, 결론, 액션 아이템(담당자, 기한), 질의/우려사항 순으로 "
                "한국어 공식 보고서 스타일로 요약해 주세요.\n"
                "아래 포맷을 반드시 지켜서 마크다운 형식으로 출력:\n"
                "### 회의 요약\n"
                "**주제:** ...\n\n"
                "**주요 논의사항:**\n"
                "- ...\n\n"
                "**결론:**\n"
                "- ...\n\n"
                "**실행 계획:**\n"
                "- [담당자] ...\n\n"
                "**질의/우려사항:**\n"
                "- ...\n"
            )
        ),
        (
            "human",
            "다음 대화 내용을 위 포맷에 맞춰 요약해줘:\n{input}"
        ),
    ])
    summarize_chain = summarize_prompt | llm
    summary_report = await summarize_chain.ainvoke({"input": conversation_to_summarize})
    return getattr(summary_report, "content", "요약 보고서 생성에 실패했습니다.")


# --- LangChain 에이전트 설정 ---
tools = [create_schedule, get_schedule, summarize_channel_conversations]

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "당신은 대학생 협업툴의 AI 어시스턴트입니다. 사용자의 자연어 요청에 맞춰 "
                "아래의 도구(Tool)를 조합하여 일정관리, 회의 대화 요약, 일정 조회 등 다양한 업무를 자동화해줍니다.\n"
                "모든 기능 실행시 반드시 'user_id', 'channel_id', 'jwt_token'을 정확하게 전달해야 합니다.\n"
                "각 도구 설명을 참고하여 사용자의 의도를 가장 잘 만족시킬 수 있는 Tool만 사용하세요.\n"
                "가능하면 답변은 친절하지만 간결하게, 최종 결과만 명확하게 전달하세요.\n"
                "대답이 표 형식이나 마크다운 등으로 보기 쉽게 나오면 더 좋습니다.\n"
                "현재 사용자의 ID: {user_id}, 채널 ID: {channel_id}\n"
                f"오늘 날짜: {today_str}\n"
                "\n"
                "예시)\n"
                "- '오늘 일정 알려줘' => get_schedule\n"
                "- '내일 오후 2시에 미팅 잡아줘' => create_schedule\n"
                "- '어제 회의 요약해줘' => summarize_channel_conversations (time_query: '어제')\n"
                "\n"
                "반드시 적절한 도구를 사용해서 답을 생성하세요."
            ),
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

async def run_agent(query: str, user_id: int, channel_id: int, jwt_token: str) -> str:
    """사용자 질문, 유저 ID, 채널 ID, JWT 토큰을 받아 AI 에이전트를 실행하고 답변을 반환."""
    result = await agent_executor.ainvoke({
        "input": query,
        "user_id": user_id,
        "channel_id": channel_id,
        "jwt_token": jwt_token,
    })
    return result.get("output", "죄송합니다. 답변을 생성하지 못했습니다.")
