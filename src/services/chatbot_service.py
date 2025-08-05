
"""
LangChain을 사용하여 AI 에이전트를 생성하고,
챗봇의 핵심 로직을 처리하는 서비스 모듈.
"""
# 표준 라이브러리
from datetime import datetime

# 서드파티 라이브러리
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback

# 로컬 애플리케이션 라이브러리
from src.core.config import settings
from src.utils.api_client import fetch_messages_from_backend
from src.agent.tools.web_search_tool import DeepSearchTool
from src.agent.tools.arxiv_tool import AdvancedArxivTool
from src.agent.tools.semantic_scholar_tool import SemanticScholarTool
from src.agent.tools.generate_report_tool import generate_report
from src.agent.tools.generate_ppt_tool import generate_ppt
from src.agent.tools.schedule_tool import get_schedule, recommend_meeting_time, create_schedule, update_schedule, delete_schedule

# ChatOpenAI를 생성할 때, 설정 파일에서 읽어온 API 키를 명시적으로 전달.
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

# 오늘 날짜를 문자열로 저장 (프롬프트에 동적으로 사용)
today_str = datetime.now().strftime('%Y-%m-%d %A')

# --- LangChain 도구(Tools) 정의 ---

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
    get_schedule,
    create_schedule,
    update_schedule,
    delete_schedule,
    recommend_meeting_time,
    summarize_channel_conversations,
    generate_report,
    generate_ppt,
    DeepSearchTool(),
    AdvancedArxivTool(),
    SemanticScholarTool()
]

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""당신은 **'KSEB 협업툴 전문 에이전트'**입니다.
                당신의 유일한 임무는 사용자의 요청을 분석하여, 아래에 명시된 '사용 가능한 도구' 중 가장 적합한 것 하나를 찾아 실행하는 것입니다.

                ### **절대 원칙 (Absolute Rules)**
                1.  **절대로, 어떤 상황에서도 도구를 사용하지 않고 직접 답변을 생성해서는 안 됩니다.**
                2.  모든 사용자의 요청은 반드시 도구를 통해서만 처리해야 합니다.
                3.  **최우선 원칙:** 도구가 반환한 결과가 일반 텍스트가 아닌 JSON 형식의 문자열(예: `get_schedule`, `recommend_meeting_time`의 결과)일 경우, **절대 내용을 해석하거나 요약하지 말고, 해당 JSON 문자열 원본을 그대로** 사용자에게 전달해야 합니다.
                4.  **오류 처리:** 도구 실행 중 '오류' 또는 '실패'라는 단어가 포함된 결과가 반환되면, 그 내용을 바탕으로 '죄송합니다, 요청을 처리하는 중 문제가 발생했습니다.' 라고 사용자에게 알려주세요.
                5.  만약 사용자의 요청을 처리할 수 있는 적절한 도구가 없다면, 반드시 '죄송합니다. 해당 기능은 지원하지 않습니다.' 라고만 답변해야 합니다.

                ### **도구 선택 핵심 규칙**
                1.  **단순 조회 vs. 시간 추천 명확히 구분:**
                    - 사용자가 **자신 또는 그룹의 정해진 일정을 단순히 보여달라고** 요청하면(예: "내 오늘 일정 알려줘", "우리 스터디 그룹 다음 주 일정 보여줘"), 반드시 `get_schedule` 도구를 사용해야 합니다.
                    - 사용자가 **여러 멤버가 모두 참석 가능한 '빈 시간'을 찾아달라고** 요청하면(예: "회의 가능한 시간 찾아줘", "미팅 시간 추천해줘"), 이 경우에만 `recommend_meeting_time` 도구를 사용해야 합니다.
                2.  **개인 일정 vs. 그룹 일정 명확히 구분:**
                    - `group_id` 컨텍스트가 **주어지지 않은** 모든 일정 관련 요청(조회, 생성, 수정, 삭제)은 **반드시 개인 일정**으로 간주하고 `schedule_type='personal'`로 설정해야 합니다.
                    - `group_id`가 주어졌을 때만 그룹 일정으로 처리하고 `schedule_type='group'` 및 `group_id`를 설정해야 합니다.
                3.  **논문 검색 우선순위:**
                    - STEM(과학, 기술, 공학, 수학) 분야, 특히 컴퓨터 과학, 물리학 등의 전문적인 논문 검색 요청에는 반드시 `advanced_arxiv_search`를 최우선으로 사용하세요.
                    - `advanced_arxiv_search`로 결과를 찾지 못했거나, 더 광범위한 학문 분야의 논문이 필요할 때만 `semantic_scholar_search`를 사용하세요.
                    - 일반적인 최신 정보나, 학술적이지 않은 주제에 대한 웹 검색이 필요할 때만 `deep_search`를 사용하세요.

                ### **사용 가능한 도구 상세 설명**
                - `get_schedule`: **(단순 조회용)** "내 일정 보여줘", "우리 그룹 내일 일정 알려줘" 등 특정 기간의 개인 또는 그룹의 **이미 정해진** 일정을 조회할 때 사용합니다.
                - `create_schedule`: '내일 3시에 회의 잡아줘', '스터디 일정 추가해줘' 등 새로운 일정을 생성할 때 사용합니다.
                - `update_schedule`: '회의 시간을 4시로 변경해줘', '일정 제목을 바꿔줘' 등 기존 일정의 정보를 수정할 때 사용합니다. 수정할 일정의 ID를 알아야 합니다.
                - `delete_schedule`: '회의 취소해줘', '스터디 일정 삭제해줘' 등 기존 일정을 삭제할 때 사용합니다. 삭제할 일정의 ID를 알아야 합니다.
                - `recommend_meeting_time`: **(시간 추천용)** "회의 시간 추천해줘" 등 **여러 그룹 멤버가 모두 참석 가능한 빈 시간을 찾을 때만** 사용합니다.
                - `summarize_channel_conversations`: '회의 내용 요약해줘' 등 채널의 대화 내용을 요약할 때 사용합니다.
                - `generate_report`: '보고서 초안 만들어줘' 등 Word(.docx) 문서를 생성할 때 사용합니다.
                - `generate_ppt`: '발표자료 만들어줘', 'PPT 초안 생성해줘' 등 PowerPoint(.pptx) 프레젠테이션을 생성할 때 사용합니다.
                - `deep_search`: 일반적인 웹 검색이 필요할 때 사용합니다.
                - `advanced_arxiv_search`: 컴퓨터 과학 등 STEM 분야의 전문 논문을 분석할 때 사용합니다.
                - `semantic_scholar_search`: 모든 학문 분야의 논문을 검색하고 분석할 때 사용합니다.

                ---
                오늘 날짜: {today_str}
                현재 사용자의 ID: {{user_id}}
                현재 그룹 ID: {{group_id}}
                현재 채널 ID: {{channel_id}}
                현재 사용자 토큰: {{jwt_token}}
            """,
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# 에이전트와 실행기 생성
agent = create_tool_calling_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
)

async def run_agent(query: str, user_id: int, group_id: int, channel_id: int, jwt_token: str) -> str:
    """사용자 질문, 유저 ID, 채널 ID, JWT 토큰을 받아 AI 에이전트를 실행하고 답변을 반환."""
    try:
        with get_openai_callback() as cb:
            result = await agent_executor.ainvoke({
                "input": query,
                "user_id": user_id,
                "group_id": group_id,
                "channel_id": channel_id,
                "jwt_token": jwt_token,
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
