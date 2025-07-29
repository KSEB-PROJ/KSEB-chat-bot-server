
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
from langchain_community.callbacks import get_openai_callback

# 로컬 애플리케이션 라이브러리
from src.core.config import settings
from src.agent.tools.web_search_tool import DeepSearchTool
from src.agent.tools.arxiv_tool import AdvancedArxivTool
from src.agent.tools.semantic_scholar_tool import SemanticScholarTool

# HTTP 클라이언트는 재사용하는 것이 효율적이므로 모듈 수준에서 정의.
client = httpx.AsyncClient(base_url=settings.MAIN_SERVER_URL)

# ChatOpenAI를 생성할 때, 설정 파일에서 읽어온 API 키를 명시적으로 전달.
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
        "Authorization": f"Bearer {jwt_token}",
        "X-User-ID": str(user_id)
    }
    try:
        response = await client.get(api_url, headers=headers, timeout=5.0)
        response.raise_for_status()
        messages = response.json().get("data", [])
        if not messages:
            return ""
        return "\n".join(
            f"[{datetime.fromisoformat(msg['createdAt']).strftime('%Y-%m-%d %H:%M')}] "
            f"{msg['userName']}: {msg.get('content') or '(파일)'}"
            for msg in messages
        )
    except httpx.HTTPStatusError as e:
        print(f"[fetch_messages_from_backend] 메인 서버 API 오류: {e.response.status_code} {e.response.text}")
        raise ValueError("대화 내용을 가져오는 데 실패했습니다.") from e
    except Exception as e:
        print(f"[fetch_messages_from_backend] 메시지 조회 중 알 수 없는 오류 발생: {e}")
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
                "Authorization": f"Bearer {jwt_token}"
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
                "Authorization": f"Bearer {jwt_token}"
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
    """채널의 대화 내용을 요약. '회의 요약해줘', '대화 정리해줘' 등과 같이 말할 때 사용."""
    print(f"Executing summary for user {user_id} in channel {channel_id} with time_query: '{time_query}'")
    full_conversation = await fetch_messages_from_backend(channel_id, user_id, jwt_token)
    if not full_conversation:
        return "요약할 대화 내용이 없습니다."

    conversation_to_summarize = full_conversation
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
tools = [
    create_schedule,
    get_schedule,
    summarize_channel_conversations,
    DeepSearchTool(),
    AdvancedArxivTool(),
    SemanticScholarTool()
]

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "당신은 **'KSEB 협업툴 전문 에이전트'**입니다.\n"
                "당신의 유일한 임무는 사용자의 요청을 분석하여, 아래에 명시된 '사용 가능한 도구' 중 가장 적합한 것 하나를 찾아 실행하는 것입니다.\n"
                "\n"
                "### **절대 원칙 (Absolute Rules)**\n"
                "1.  **절대로, 어떤 상황에서도 도구를 사용하지 않고 직접 답변을 생성해서는 안 됩니다.**\n"
                "2.  모든 사용자의 요청은 반드시 도구를 통해서만 처리해야 합니다.\n"
                "3.  **최우선 원칙:** 도구가 오류 없이 유의미한 결과(작업 로그 포함)를 반환했다면, 그것이 최선의 결과라고 믿고 **그 내용을 수정 없이 그대로 사용자에게 전달해야 합니다.**\n"
                "4.  만약 사용자의 요청을 처리할 수 있는 적절한 도구가 없다면, 반드시 '죄송합니다. 해당 기능은 지원하지 않습니다.' 라고만 답변해야 합니다.\n"
                "\n"
                "### **도구 선택 전략 (Tool Selection Strategy)**\n"
                "- **1순위 (기술/과학):** 질문이 컴퓨터 과학, AI, 물리, 수학 등 명확한 STEM 분야에 해당하면 `advanced_arxiv_search`를 먼저 사용하세요.\n"
                "- **2순위 (사회과학/인문학/일반):** 질문이 심리학, 사회학, 교육학 등 비-STEM 분야이거나, `advanced_arxiv_search`로 결과를 찾지 못했을 경우, `semantic_scholar_search`를 사용하세요.\n"
                "- **3순위 (웹 정보):** 위 두 가지 학술 검색으로도 답을 찾을 수 없거나, 최신 뉴스/트렌드에 대한 질문일 경우에만 `deep_search`를 사용하세요.\n"
                "\n"
                "### **사용 가능한 도구**\n"
                "- `create_schedule`: '일정 추가해줘', '미팅 잡아줘' 등 새로운 일정을 생성할 때 사용합니다.\n"
                "- `get_schedule`: '오늘 내 일정 보여줘', '내일 뭐 있지?' 등 특정 날짜의 일정을 조회할 때 사용합니다.\n"
                "- `summarize_channel_conversations`: '회의 내용 요약해줘', '채팅 정리해줘' 등 채널의 대화 내용을 요약할 때 사용합니다.\n"
                "- `deep_search`: 일반적인 웹 검색이 필요할 때 사용합니다.\n"
                "- `advanced_arxiv_search`: 컴퓨터 과학, AI 등 STEM 분야의 전문 논문을 심층 분석할 때 사용합니다.\n"
                "- `semantic_scholar_search`: 심리학, 사회과학 등 모든 학문 분야의 논문을 검색하고 분석할 때 사용합니다.\n"
                "\n"
                "--- \n"
                f"오늘 날짜: {today_str}\n"
                "현재 사용자의 ID: {user_id}\n"
                "현재 채널 ID: {channel_id}\n"
                "현재 사용자 토큰: {jwt_token}\n"
            ),
        ),
        ("human", "{input}"),
        # 에이전트의 이전 작업 기록을 전달하는 플레이스홀더.
        ("placeholder", "{agent_scratchpad}"),
    ]
)


agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
)

async def run_agent(query: str, user_id: int, channel_id: int, jwt_token: str) -> str:
    """사용자 질문, 유저 ID, 채널 ID, JWT 토큰을 받아 AI 에이전트를 실행하고 답변을 반환."""
    try:
        with get_openai_callback() as cb:
            result = await agent_executor.ainvoke({
                "input": query,
                "user_id": user_id,
                "channel_id": channel_id,
                "jwt_token": jwt_token,
                # 무한 루프 방지를 위해 에이전트의 작업 기록(scratchpad)을 전달.
                "agent_scratchpad": []
            })

            # 콜백 객체(cb)에 기록된 토큰 정보를 출력.
            print("\n" + "="*40)
            print("Token Usage Details:")
            print(f"  - Total Tokens: {cb.total_tokens}")
            print(f"  - Prompt Tokens: {cb.prompt_tokens}")
            print(f"  - Completion Tokens: {cb.completion_tokens}")
            print(f"  - Total Cost (USD): ${cb.total_cost:.6f}")
            print("="*40 + "\n")
            
        return result.get("output", "죄송합니다. 답변을 생성하지 못했습니다.")
    # 에이전트 실행의 마지막 안전망으로, 모든 예외를 처리하여 서버가 중단되지 않게 함.
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"에이전트 실행 중 오류 발생: {e}")
        return "죄송합니다, 요청을 처리하는 중에 예상치 못한 오류가 발생했습니다. 질문을 조금 더 구체적으로 바꿔서 다시 시도해 주시겠어요?"
    
