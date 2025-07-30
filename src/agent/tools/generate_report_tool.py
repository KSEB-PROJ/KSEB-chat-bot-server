# src/agent/tools/generate_report_tool.py
import os
import json
import uuid
import tempfile
from datetime import datetime
from docx import Document
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.utils.api_client import fetch_messages_from_backend
from .web_search_tool import DeepSearchTool

# LLM 및 도구 인스턴스 초기화
llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0.2, api_key=settings.OPENAI_API_KEY)
web_search_tool = DeepSearchTool()

# 이 파일의 현재 위치를 기준으로 프로젝트 루트 경로를 계산합니다.
PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# 사용자의 커스텀 템플릿을 직접 사용하도록 경로 변경
TEMPLATE_PATH = os.path.join(PROJ_ROOT, "src", "templates", "docx", "reports", "user_custom_template.docx")

def assemble_docx_from_outline(outline_json: dict, path: str):
    """LLM이 생성한 JSON 개요를 기반으로, 사용자의 스타일 템플릿을 사용하여 Word 문서를 생성합니다."""
    
    try:
        # 사용자의 템플릿을 직접 엽니다.
        doc = Document(TEMPLATE_PATH)
        # 기존 내용을 모두 지웁니다. (스타일은 유지됨)
        for para in doc.paragraphs:
            p = para._element
            p.getparent().remove(p)
    except Exception as e:
        print(f"Warning: Template not found at {TEMPLATE_PATH} or is invalid. Creating a blank document. Error: {e}")
        doc = Document()

    # --- 1. 표지 생성 (Word 기본 스타일 사용) ---
    title = outline_json.get("title", "제목 없음")
    doc.add_heading(title, level=0) # 'Title' 스타일
    doc.add_paragraph(f"작성일: {datetime.now().strftime('%Y-%m-%d')}")
    doc.add_paragraph("소속: KSEB대학교 AI융합학과")
    doc.add_paragraph("작성자: AI 어시스턴트")
    doc.add_page_break()

    # --- 2. 목차 생성 ---
    doc.add_heading("목차", level=1) # 'Heading 1' 스타일
    for item in outline_json.get("table_of_contents", []):
        doc.add_paragraph(item, style='List Bullet')
    doc.add_page_break()

    # --- 3. 본문 생성 ---
    for section in outline_json.get("sections", []):
        doc.add_heading(section.get('section_title', '제목 없음'), level=2) # 'Heading 2' 스타일
        
        p = doc.add_paragraph()
        p.add_run('[작성 가이드]').bold = True
        doc.add_paragraph(section.get('guideline', '')).italic = True
        
        if section.get('key_points'):
            doc.add_paragraph('') # 여백
            p = doc.add_paragraph()
            p.add_run('핵심 포인트:').bold = True
            for point in section['key_points']:
                text = str(point).strip().lstrip('- ').strip()
                doc.add_paragraph(text, style='List Bullet')

        if section != outline_json.get("sections", [])[-1]:
            doc.add_page_break()

    doc.save(path)

@tool
async def generate_report(topic: str, user_id: int, channel_id: int, jwt_token: str) -> str:
    """
    주제(topic)와 관련된 채널 대화 및 웹 리서치 결과를 종합하여,
    체계적인 구조와 전문적인 디자인을 갖춘 Word 보고서 초안을 생성하고 다운로드 링크를 반환합니다.
    """
    print(f"Executing final generate_report for user {user_id} on topic: '{topic}'")

    # --- 1단계: 실시간 정보 수집 ---
    print("   - 1.1: Fetching channel conversation...")
    chat_history = await fetch_messages_from_backend(channel_id, user_id, jwt_token)
    
    print("   - 1.2: Performing web search...")
    web_research_results = web_search_tool._run(f"{topic}에 대한 최신 정보, 통계, 전문가 의견")
    
    combined_info = f"주제: {topic}\n\n[채널 대화 내용]:\n{chat_history}\n\n[웹 리서치 결과]:\n{web_research_results}"
    print("   - 1.3: Data collection complete.")

    # --- 2단계: LLM으로 보고서 구조 설계 (JSON 생성) ---
    print("   - 2.1: Generating report outline with LLM...")
    system_prompt = """
    당신은 명문대 글쓰기 센터의 전문 튜터입니다. 당신의 임무는 주어진 주제와 핵심 정보들을 바탕으로, 논리적이고 체계적인 '대학생 연구 보고서'의 개요를 JSON 형식으로 생성하는 것입니다.

    **보고서 작성 원칙:**
    1.  **구조:** 서론-본론-결론의 명확한 3단 구조를 반드시 따릅니다.
    2.  **목차:** '본론'은 분석의 깊이를 더하기 위해 2~3개의 구체적인 소주제로 나누어 목차를 구성합니다.
    3.  **가이드라인:** 각 섹션(서론, 본론1, 본론2, 결론 등)마다, 학생이 어떤 내용을 작성해야 하는지 상세하고 친절한 '가이드라인'을 제시해야 합니다.
    4.  **핵심 포인트:** 주어진 '핵심 정보'에서 가장 중요한 내용들을 추출하여, 각 섹션과 관련된 '핵심 포인트'로 2~4개씩 포함시켜야 합니다.
    5.  **출력:** 다른 설명 없이, 오직 JSON 객체만을 생성해야 합니다.

    **출력 JSON 형식:**
    {{
      "title": "보고서 제목",
      "table_of_contents": ["I. 서론", "II. 본론 1: [소주제]", "III. 본론 2: [소주제]", "IV. 결론"],
      "sections": [
        {{"section_title": "I. 서론", "guideline": "[연구 배경, 문제 제기, 연구의 중요성 및 보고서의 구성 소개]", "key_points": ["[포인트 1]", "[포인트 2]"]}},
        {{"section_title": "II. 본론 1: ...", "guideline": "[첫 번째 소주제에 대한 심층 분석 및 데이터 제시]", "key_points": [...]}},
        {{"section_title": "III. 본론 2: ...", "guideline": "[두 번째 소주제에 대한 사례 분석 및 전문가 의견]", "key_points": [...]}},
        {{"section_title": "IV. 결론", "guideline": "[본론 내용 요약, 연구의 시사점 및 향후 과제 제시]", "key_points": [...]}}
      ]
    }}
    """
    human_prompt = "주제: {topic}\n\n[수집된 핵심 정보]:\n{information}"
    
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_prompt)])
    chain = prompt | llm
    
    try:
        response = await chain.ainvoke({"topic": topic, "information": combined_info})
        json_string = response.content.strip().replace("```json", "").replace("```", "").strip()
        outline_json = json.loads(json_string)
        print("   - 2.2: Report outline generated successfully.")
    except Exception as e:
        print(f"Error creating report outline: {e}")
        return "보고서 개요 생성에 실패했습니다. LLM 응답을 처리할 수 없습니다."

    # --- 3단계: Word 파일 조립 및 생성 ---
    print("   - 3.1: Assembling Word document...")
    output_filename = f"{uuid.uuid4()}.docx"
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, output_filename)

    try:
        assemble_docx_from_outline(outline_json, output_path)
        print(f"   - 3.2: ✅ Report successfully generated at: {output_path}")
    except Exception as e:
        print(f"Error generating report file: {e}")
        return "보고서 파일을 생성하는 중 오류가 발생했습니다."

    # --- 4단계: 다운로드 링크 반환 ---
    download_url = f"http://localhost:8001/api/v1/download/{output_filename}"
    return f"'{outline_json.get('title', topic)}' 보고서 초안이 생성되었습니다. [여기에서 다운로드]({download_url})하세요."