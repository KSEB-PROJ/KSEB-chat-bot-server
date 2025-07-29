"""
Semantic Scholar에서 학술 논문을 검색하고, 그 내용을 요약하는 모듈.
httpx를 사용하여 API를 직접 호출하며, 한국어 쿼리를 영어로 자동 번역하고,
상위 3개의 검색 결과를 종합하여 보고.
"""

import os
import re
import tempfile
import asyncio
import time
from typing import Optional, List, Dict, Any, ClassVar

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
    model=settings.OPENAI_MODEL, temperature=0, api_key=settings.OPENAI_API_KEY
)


class SemanticScholarTool(BaseTool):
    """
    Semantic Scholar에서 모든 분야의 학술 논문을 검색하고,
    Open Access PDF가 있는 경우 분석하여 한국어로 요약하는 도구.
    """

    name: str = "semantic_scholar_search"
    description: str = (
        "Use this tool to find and summarize up to 3 academic papers from all fields, including social sciences, medicine, and humanities. "
        "It automatically generates effective English search queries from Korean."
    )

    BASE_URL: ClassVar[str] = "https://api.semanticscholar.org/graph/v1"

    def _search_papers(self, query: str) -> List[Dict[str, Any]]:
        """httpx를 사용하여 Semantic Scholar API를 직접 호출."""
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": query,
            "limit": 3,  # 3개로 제한
            "fields": "title,abstract,url,year,authors,openAccessPdf",
        }
        headers = (
            {"x-api-key": settings.SEMANTIC_SCHOLAR_API_KEY}
            if settings.SEMANTIC_SCHOLAR_API_KEY
            else {}
        )
        try:
            with httpx.Client(timeout=30.0, headers=headers) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except httpx.TimeoutException:
            print(f"[Semantic Scholar] API 호출 실패: 타임아웃 (30초) - {query}")
            return []
        except Exception as e:
            print(f"[Semantic Scholar] API 호출 실패: {e}")
            return []

    def _translate_query_to_english(self, query: str) -> List[str]:
        """사용자의 한국어 쿼리를 여러 개의 영어 검색어로 변환."""
        print(f"    [쿼리 생성] 한국어 쿼리 분석 및 영어 검색어 생성 시도: '{query}'")
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert academic researcher. Your task is to analyze the following Korean user query and generate up to 3 "
                    "diverse and effective English search keyword phrases for an academic database. Provide only the keyword phrases, "
                    "each on a new line, without any numbering or extra text.",
                ),
                ("human", "{korean_query}"),
            ]
        )
        chain = prompt | llm
        response = chain.invoke({"korean_query": query})
        queries = [q.strip() for q in response.content.split("\n") if q.strip()]
        print(f"    [쿼리 생성] 완료: {queries}")
        return queries

    def _analyze_paper(self, paper: dict) -> Optional[str]:
        """단일 논문을 분석하고 요약."""
        pdf_url = (
            paper.get("openAccessPdf", {}).get("url")
            if paper.get("openAccessPdf")
            else None
        )

        if pdf_url:
            print(f"    [PDF 발견] Open Access PDF 발견: {paper.get('title', 'N/A')}")
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = self._download_pdf(pdf_url, temp_dir)
                if pdf_path:
                    extracted_text = self._extract_intro_and_conclusion(pdf_path)
                    if (
                        "Failed" not in extracted_text
                        and "Could not find" not in extracted_text
                    ):
                        return self._summarize_text(
                            extracted_text, paper.get("title", "N/A")
                        )

        print(
            f"    [초록 요약] PDF를 분석할 수 없어 초록을 요약합니다: {paper.get('title', 'N/A')}"
        )
        return self._summarize_text(
            paper.get("abstract", ""), paper.get("title", "N/A")
        )

    # pylint: disable=arguments-differ
    def _run(
        self,
        query: str,
        run_manager: Optional[
            CallbackManagerForToolRun
        ] = None,  # pylint: disable=unused-argument
    ) -> str:
        """지능형 쿼리 생성 -> 순차 검색 -> 상위 3개 결과 종합 로직 실행."""
        process_log = [f"🔍 **'{query}'에 대한 전체 학술 자료 분석을 시작합니다...**\n"]

        english_queries = self._translate_query_to_english(query)
        process_log.append(
            "🔄 **검색어 생성:** " + ", ".join(f"'{q}'" for q in english_queries)
        )

        all_results = []
        time.sleep(1)  # 첫 API 호출 전 선제적 딜레이
        for eq in english_queries:
            print(f"[Semantic Scholar] API 호출 시작: '{eq}'")
            papers = self._search_papers(eq)
            print(f"[Semantic Scholar] API 호출 완료: {len(papers)}개 결과 수신.")
            if papers:
                all_results.extend(papers)
            if len(all_results) >= 3:
                break
            time.sleep(2)

        if not all_results:
            return "해당 주제에 대한 논문을 Semantic Scholar에서 찾을 수 없습니다."

        process_log.append(
            f"\n📄 **총 {len(all_results[:3])}개의 관련 논문을 분석합니다.**\n"
        )

        for i, paper in enumerate(all_results[:3]):  # 최대 3개만 분석
            process_log.append(f"--- \n### **분석 {i+1}: {paper.get('title', 'N/A')}**")

            korean_summary = self._analyze_paper(paper)
            process_log.append(korean_summary or "요약 생성에 실패했습니다.")
            process_log.append(
                f"\n- **저자**: {', '.join(author['name'] for author in paper.get('authors', []))}"
            )
            process_log.append(f"- **게재 연도**: {paper.get('year', 'N/A')}")
            process_log.append(f"- **링크**: {paper.get('url', 'N/A')}\n")

        return "\n".join(process_log)

    def _download_pdf(self, pdf_url: str, dir_path: str) -> Optional[str]:
        """PDF를 임시 디렉토리에 다운로드하고 파일 경로를 반환."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            with httpx.Client(
                timeout=60.0, headers=headers, follow_redirects=True
            ) as client:
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
            full_text = " ".join(
                page.get_text("text", sort=True) for page in doc
            ).replace("\n", " ")
            doc.close()
            intro_start_match = re.search(
                r"(1\s*\.?\s*)?INTRODUCTION", full_text, re.IGNORECASE
            )
            if not intro_start_match:
                return "Could not find introduction."
            intro_text = full_text[intro_start_match.start() :]
            intro_end_match = re.search(
                r"2\s*\.?\s*(BACKGROUND|RELATED WORK|PRELIMINARIES)",
                intro_text,
                re.IGNORECASE,
            )
            introduction = (
                intro_text[: intro_end_match.start()]
                if intro_end_match
                else intro_text[:4000]
            )
            conclusion_text = ""
            conclusion_start_match = re.search(
                r"CONCLUSION|DISCUSSION", full_text, re.IGNORECASE
            )
            if conclusion_start_match:
                references_start_match = re.search(
                    r"REFERENCES|ACKNOWLEDGEMENTS",
                    full_text[conclusion_start_match.start() :],
                    re.IGNORECASE,
                )
                if references_start_match:
                    conclusion_text = full_text[
                        conclusion_start_match.start() : conclusion_start_match.start()
                        + references_start_match.start()
                    ]
                else:
                    conclusion_text = full_text[conclusion_start_match.start() :]
            return f"--- INTRODUCTION ---\n{introduction}\n\n--- CONCLUSION ---\n{conclusion_text}"
        except Exception:  # pylint: disable=broad-exception-caught
            return "Failed to extract text from PDF."

    def _summarize_text(self, text: str, title: str) -> str:
        """추출된 텍스트를 한국어로 요약."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert research paper analyst. Your task is to synthesize the provided Introduction and Conclusion "
                    "of an academic paper into a comprehensive yet easy-to-understand summary in Korean. "
                    "Focus on the paper's core problem, methodology, key findings, and implications.",
                ),
                (
                    "human",
                    "Please summarize the following content from the paper titled '{title}':\n\n{text}",
                ),
            ]
        )
        chain = prompt | llm
        summary = chain.invoke({"text": text, "title": title})
        return summary.content

    # pylint: disable=arguments-differ
    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """비동기 환경에서 동기 함수인 _run을 실행."""
        return await asyncio.to_thread(self._run, query, run_manager=run_manager)
