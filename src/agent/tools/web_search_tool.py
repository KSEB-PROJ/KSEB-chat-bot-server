"""
고성능 웹 검색을 위한 DeepSearchTool 정의 모듈.

이 모듈은 Google Search와 Jina AI Reader를 결합하여,
빠르고 정확하게 웹페이지의 핵심 콘텐츠를 추출하는 커스텀 도구.
"""
import os
from typing import Optional

import httpx
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from langchain_google_community import GoogleSearchAPIWrapper

from ...core.config import settings

# --- 1. 구글 검색을 통한 URL 확보 ---
# 환경 변수에서 API 키를 로드.
os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
os.environ["GOOGLE_CSE_ID"] = settings.GOOGLE_CSE_ID

search = GoogleSearchAPIWrapper()


# --- 2. Jina Reader를 통한 본문 추출 함수 ---
def scrape_with_jina(url: str) -> str:
    """
    Jina Reader API를 사용해 주어진 URL 내용 스크랩.
    """
    jina_reader_url = f"https://r.jina.ai/{url}"
    try:
        with httpx.Client() as client:
            response = client.get(jina_reader_url, timeout=30.0)
            response.raise_for_status()  # HTTP 오류가 발생하면 예외 발생.
            return response.text
    except httpx.RequestError as e:
        return f"Error fetching {url}: {e}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"An unexpected error occurred: {e}"


# --- 3. 두 기능을 결합한 커스텀 도구 생성 ---
class DeepSearchTool(BaseTool):
    """
    Google Search와 Jina Reader를 결합한 웹 검색 도구.
    """
    name: str = "deep_search"
    description: str = (
        "A tool for performing deep web searches. "
        "It finds relevant URLs with Google Search, scrapes their content using Jina AI Reader, "
        "and returns a summarized result. Use this for questions about recent events or specific topics."
    )

    # pylint: disable=arguments-differ
    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None  # pylint: disable=unused-argument
    ) -> str:
        """
        쿼리를 실행하고 검색된 내용을 반환. (동기 방식)
        """
        # 1. Google Search로 상위 3개 결과의 URL을 가져옴.
        search_results = search.results(query, num_results=3)

        if not search_results:
            return "No search results found."

        urls = [result["link"] for result in search_results if "link" in result]
        if not urls:
            return "No valid URLs found in search results."

        # 2. 각 URL의 내용을 Jina Reader로 스크랩.
        scraped_contents = []
        for url in urls:
            content = scrape_with_jina(url)
            # 결과가 너무 길 경우를 대비해 일부만 사용
            if len(content) > 5000:
                content = content[:5000] + "... (truncated)"
            scraped_contents.append(f"--- Content from {url} ---\n{content}")

        return "\n\n".join(scraped_contents)

    # pylint: disable=arguments-differ
    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None  # pylint: disable=unused-argument
    ) -> str:
        """
        쿼리를 실행하고 검색된 내용을 반환. (비동기 방식)
        """
        # 아직은 동기 방식을 사용하지만 혹시 모르니...
        return self._run(query)
    