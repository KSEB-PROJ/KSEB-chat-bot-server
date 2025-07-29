"""arXiv.org에서 학술 논문을 검색하고, PDF 본문을 분석하여
심층적인 한국어 요약을 제공하는 모듈.
사용자의 한국어 쿼리를 영어 검색어들로 변환하여 검색 성능 향상,
상위 3개의 검색 결과를 종합하여 보고.
"""
import os
import re
import tempfile
import asyncio
import time
from typing import Optional, List

import arxiv
import fitz  # PyMuPDF
import httpx
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ...core.config import settings

# LLM 인스턴스
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

class AdvancedArxivTool(BaseTool):
    """
    arXiv.org에서 논문을 검색하고, PDF 본문을 분석하여
    심층적인 한국어 요약을 제공하는 도구.
    """
    name: str = "advanced_arxiv_search"
    description: str = (
        "Use this tool to find and deeply summarize up to 3 academic papers from arXiv, especially for STEM fields like Computer Science and AI. "
        "It automatically translates Korean queries to English."
    )

    def _translate_query_to_english(self, query: str) -> List[str]:
        """사용자의 한국어 쿼리를 여러 개의 효과적인 영어 검색어로 변환."""
        print(f"    [쿼리 생성] 한국어 쿼리 분석 및 영어 검색어 생성 시도: '{query}'")
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert academic researcher. Your task is to analyze the following Korean user query and generate up to 3 "
                "diverse and effective English search keyword phrases for an academic database. Provide only the keyword phrases, "
                "each on a new line, without any numbering or extra text."
            ),
            ("human", "{korean_query}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"korean_query": query})
        queries = [q.strip() for q in response.content.split('\n') if q.strip()]
        print(f"    [쿼리 생성] 완료: {queries}")
        return queries

    def _analyze_paper(self, paper: arxiv.Result) -> Optional[str]:
        """단일 논문을 다운로드, 분석, 요약하는 파이프라인."""
        process_log = []
        with tempfile.TemporaryDirectory() as temp_dir:
            process_log.append("    - 📥 PDF 다운로드 시도...")
            pdf_path = self._download_pdf(paper.pdf_url, temp_dir)
            if not pdf_path:
                process_log.append("    - ⚠️ **분석 실패:** PDF를 다운로드할 수 없습니다.")
                return "\n".join(process_log)

            process_log.append("    - 📑 PDF 텍스트 추출 및 분석 시도...")
            extracted_text = self._extract_intro_and_conclusion(pdf_path)
            if "Failed" in extracted_text or "Could not find" in extracted_text:
                process_log.append("    - ⚠️ **분석 실패:** PDF 구조가 복잡하여 서론/결론을 추출할 수 없습니다. 초록으로 대체합니다.")
                extracted_text = paper.summary
            else:
                process_log.append("    - ✅ PDF 분석 완료.")

            process_log.append("    - ✍️ 한국어 요약 생성 시도...")
            summary = self._summarize_text(extracted_text, paper.title)
            process_log.append("    - ✅ 요약 생성 완료.")
            process_log.append(f"\n{summary}") # 최종 요약본 추가

            return "\n".join(process_log)

    # pylint: disable=arguments-differ
    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None  # pylint: disable=unused-argument
    ) -> str:
        """'지능형 쿼리 생성 -> 순차 검색 -> 상위 3개 결과 종합 로직 실행."""
        process_log = [f"🔍 **'{query}'에 대한 arXiv 논문 분석을 시작합니다...**\n"]
        
        english_queries = self._translate_query_to_english(query)
        process_log.append("🔄 **검색어 생성:** " + ", ".join(f"'{q}'" for q in english_queries))

        all_results = []
        for eq in english_queries:
            print(f"[Arxiv Search] API 호출 시작: '{eq}'")
            try:
                search = arxiv.Search(query=eq, max_results=3, sort_by=arxiv.SortCriterion.Relevance)
                results = list(search.results())
                print(f"[Arxiv Search] API 호출 완료: {len(results)}개 결과 수신.")
                if results:
                    all_results.extend(results)
                if len(all_results) >= 3:
                    break
                time.sleep(2)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[Arxiv Search] API 호출 실패: {e}")
                process_log.append(f"\n- ⚠️ **오류:** '{eq}' 검색 중 arXiv.org 연결에 실패했습니다.")
                continue
        
        if not all_results:
            return "해당 주제에 대한 논문을 arXiv에서 찾을 수 없습니다."

        process_log.append(f"\n📄 **총 {len(all_results[:3])}개의 관련 논문을 분석합니다.**\n")

        for i, paper in enumerate(all_results[:3]):
            process_log.append(f"--- \n### **분석 {i+1}: {paper.title}**")
            
            analysis_report = self._analyze_paper(paper)
            process_log.append(analysis_report or "요약 생성에 실패했습니다.")
            process_log.append(f"\n- **저자**: {', '.join(author.name for author in paper.authors)}")
            process_log.append(f"- **게재일**: {paper.published.date()}")
            process_log.append(f"- **링크**: {paper.entry_id}\n")

        return "\n".join(process_log)

    def _download_pdf(self, pdf_url: str, dir_path: str) -> Optional[str]:
        """PDF를 임시 디렉토리에 다운로드하고 파일 경로 반환."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
                response = client.get(pdf_url)
                response.raise_for_status()
                filepath = os.path.join(dir_path, "temp_paper.pdf")
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def _extract_intro_and_conclusion(self, filepath: str) -> str:
        """PDF에서 서론과 결론 부분의 텍스트 추출."""
        try:
            doc = fitz.open(filepath)
            full_text = " ".join(page.get_text("text", sort=True) for page in doc).replace('\n', ' ')
            doc.close()
            intro_start_match = re.search(r"(1\s*\.?\s*)?INTRODUCTION", full_text, re.IGNORECASE)
            if not intro_start_match:
                return "Could not find introduction."
            intro_text = full_text[intro_start_match.start():]
            intro_end_match = re.search(r"2\s*\.?\s*(BACKGROUND|RELATED WORK|PRELIMINARIES)", intro_text, re.IGNORECASE)
            introduction = intro_text[:intro_end_match.start()] if intro_end_match else intro_text[:4000]
            conclusion_text = ""
            conclusion_start_match = re.search(r"CONCLUSION|DISCUSSION", full_text, re.IGNORECASE)
            if conclusion_start_match:
                references_start_match = re.search(r"REFERENCES|ACKNOWLEDGEMENTS", full_text[conclusion_start_match.start():], re.IGNORECASE)
                if references_start_match:
                    conclusion_end_index = conclusion_start_match.start() + references_start_match.start()
                    conclusion_text = full_text[conclusion_start_match.start():conclusion_end_index]
                else:
                    conclusion_text = full_text[conclusion_start_match.start():]
            return f"--- INTRODUCTION ---\n{introduction}\n\n--- CONCLUSION ---\n{conclusion_text}"
        except Exception:  # pylint: disable=broad-exception-caught
            return "Failed to extract text from PDF."

    def _summarize_text(self, text: str, title: str) -> str:
        """추출된 텍스트를 한국어로 요약."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a professional academic reviewer. Your task is to analyze the provided text (Introduction and Conclusion of a paper) and write a detailed analysis report in Korean, structured with the following sections:\n\n"
             "**1. 문제 제기 (Problem Statement):** 이 연구가 해결하고자 하는 핵심 문제는 무엇인가?\n"
             "**2. 제안 방법론 (Proposed Method):** 이 문제를 해결하기 위해 어떤 독창적인 방법이나 접근법을 제안하는가?\n"
             "**3. 핵심 결과 및 의의 (Key Results & Significance)::** 연구를 통해 무엇을 발견했으며, 이 결과가 해당 분야에 어떤 중요한 기여를 하는가? (예: 성능 향상, 새로운 가능성 제시 등)\n"
             "**4. 예상 활용 분야 (Potential Applications):** 이 연구 결과가 실제로 어디에 응용될 수 있는가?"),
            ("human", "Please analyze the following content from the paper titled '{title}':\n\n{text}"),
        ])
        chain = prompt | llm
        summary = chain.invoke({"text": text, "title": title})
        return summary.content

    # pylint: disable=arguments-differ
    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """비동기 환경에서 동기 함수인 _run을 실행."""
        return await asyncio.to_thread(self._run, query, run_manager=run_manager)
