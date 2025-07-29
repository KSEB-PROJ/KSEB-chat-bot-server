"""
LangChain 기반 AI 챗봇 서비스 통합 모듈 (일정, 요약, 검색/리서치 모두 포함)
"""

from datetime import datetime
from typing import List
import httpx

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.agent.tools.web_search import advanced_web_search, refine_search_query
from src.agent.tools.web_reader import read_web_page

# --- 글로벌 객체 한 번만 선언 ---
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

main_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "당신은 **최고의 AI 리서처 어시스턴트**입니다. 사용자의 어떤 질문에도 가장 정확하고 깊이 있는 답변을 제공합니다.\n"
            "일정/대화/요약/스케줄 등은 전문 툴을, 리서치·검색·요약·정보 비교 등은 웹검색/리더를 사용하세요.\n"
            "---\n"
            f"오늘 날짜: {datetime.now().strftime('%Y-%m-%d %A')}\n"
            "현재 사용자의 ID: {user_id}\n"
            "현재 채널 ID: {channel_id}\n"
            "현재 사용자 토큰: {jwt_token}\n"
        ),
    ),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

client = httpx.AsyncClient(base_url=settings.MAIN_SERVER_URL)

# --- 일정 관리 툴 ---
@tool
async def create_schedule(title: str, start_time: str, end_time: str, user_id: int, jwt_token: str) -> str:
    """새로운 개인 일정 생성"""
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
    """특정 날짜의 사용자 일정을 조회"""
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

# --- 대화 요약 툴 ---
async def fetch_messages_from_backend(channel_id: int, user_id: int, jwt_token: str) -> str:
    """채널의 전체 대화 내역을 메인 서버 API에서 가져옴"""
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

@tool
async def summarize_channel_conversations(user_id: int, channel_id: int, jwt_token: str, time_query: str = "all") -> str:
    """채널의 대화 내용을 요약"""
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
                    f"오늘은 {datetime.now().strftime('%Y-%m-%d %A')}입니다. 전체 대화 로그는 아래와 같고, 각 행은 '[YYYY-MM-DD HH:MM] 작성자: 내용' 형태입니다.\n"
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

# --- 심층 리서치 체인 ---
async def summarize_chunks(chunks: List[str]) -> List[str]:
    """각 chunk를 LLM이 요약"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "아래 chunk를 5000자 내외로 표/코드/결론/팩트 위주로 요약해줘."),
        ("human", "{input}")
    ])
    summaries = []
    for chunk in chunks:
        summary = await (prompt | llm).ainvoke({"input": chunk})
        summaries.append(getattr(summary, "content", chunk[:1000]))
    return summaries

async def compare_summaries(summaries: List[str], urls: List[str]) -> str:
    """여러 출처별 요약을 LLM이 비교 분석"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "아래 여러 출처별 요약을 비교해서, 공통점/차이점/팩트오류/신뢰도 순서로 정리해줘."),
        ("human", "출처/요약 목록:\n" + "\n\n".join([f"{u}\n{s}" for u, s in zip(urls, summaries)]))
    ])
    result = await (prompt | llm).ainvoke({})
    return getattr(result, "content", "")

async def deep_research(query: str, max_results: int = 3) -> str:
    """리서치 전용 심층 체인"""
    refined = await refine_search_query.ainvoke({"query": query})
    results = await advanced_web_search.ainvoke({"query": refined, "max_results": max_results})

    urls, all_summaries = [], []
    for r in results:
        url = r['url']
        urls.append(url)
        chunks = await read_web_page.ainvoke({"url": url})
        summaries = await summarize_chunks(chunks)
        all_summaries.append(" ".join(summaries))
    factcheck = await compare_summaries(all_summaries, urls)
    report_prompt = ChatPromptTemplate.from_messages([
        ("system",
            "아래 factcheck_report, 원문 요약 바탕으로, 실무·전문가 관점의 심층 리포트로 작성. "
            "적용법, 코드, FAQ, 반론, 신뢰도·최신성 구조화. 참고 출처 반드시 포함."
        ),
        ("human",
            "질문: {user_query}\n\nFactCheck: {factcheck}\n\n원문 요약:\n{all_summaries}\n"
        )
    ])
    report = await (report_prompt | llm).ainvoke({
        "user_query": query,
        "factcheck": factcheck,
        "all_summaries": "\n\n".join(all_summaries),
    })
    return getattr(report, "content", "최종 분석 실패")

# --- 에이전트 세팅 ---
tools = [
    create_schedule,
    get_schedule,
    summarize_channel_conversations,
    advanced_web_search,
    read_web_page
]
agent = create_tool_calling_agent(llm, tools, main_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
)

# --- 메인 서비스 엔드포인트 ---
async def run_agent(query: str, user_id: int, channel_id: int, jwt_token: str) -> str:
    """
    질문 의도/키워드에 따라 자동 분기:
    일정, 대화, 요약, 스케줄, 회의, 생성, 수정 등은 기존 AgentExecutor,
    그 외 정보 검색/리서치/분석은 LLM 기반 심층 체인으로 처리.
    """
    key = query.lower()
    if any(word in key for word in ["일정", "대화", "채널", "요약", "스케줄", "미팅", "생성", "수정", "삭제"]):
        try:
            result = await agent_executor.ainvoke({
                "input": query,
                "user_id": user_id,
                "channel_id": channel_id,
                "jwt_token": jwt_token,
                "agent_scratchpad": []
            })
            return result.get("output", "죄송합니다. 답변을 생성하지 못했습니다.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"에이전트 실행 중 오류 발생: {e}")
            return "죄송합니다, 요청을 처리하는 중에 오류가 발생했습니다."
    # 검색/리서치/분석류는 LLM 심층 체인으로
    return await deep_research(query, max_results=3)
