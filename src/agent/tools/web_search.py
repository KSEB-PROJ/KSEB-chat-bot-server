"""
고급 웹 검색 도구 (Tavily API + LLM 쿼리 자동화)
"""

from typing import Literal, List, Dict
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from src.core.config import settings

llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

@tool
async def refine_search_query(query: str) -> str:
    """
    LLM이 검색 쿼리를 더 구체적이고 효율적으로 변환
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "아래 질문을 웹 검색에 최적화된 최신 구체 검색어로 변환. 키워드/연도/핵심 속성 강조."),
        ("human", "{input}")
    ])
    result = await (prompt | llm).ainvoke({"input": query})
    return getattr(result, "content", query)

@tool
async def advanced_web_search(
    query: str,
    search_depth: Literal["basic", "advanced"] = "advanced",
    include_images: bool = False,
    max_results: int = 5,
    include_opposite: bool = True
) -> List[Dict]:
    """
    LLM이 정제한 검색 쿼리와, '비판/반론' 쿼리를 Tavily에서 동시에 검색(중복 URL 제거)
    """
    if not query or len(query.strip()) < 2:
        return [{"error": "검색할 내용을 2글자 이상 입력해주세요."}]

    wrapper = TavilySearchAPIWrapper(tavily_api_key=settings.tavily_api_key)
    queries = [query]
    if include_opposite:
        queries.append(query + " 단점" if "단점" not in query else query + " 반론")
    all_results = []
    for q in queries:
        try:
            res = await wrapper.results_async(
                q,
                max_results=max_results,
                search_depth=search_depth,
                include_images=include_images,
            )
            results = res.get("results") if isinstance(res, dict) else res
            if results:
                all_results += results
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    # URL 기준 중복 제거
    seen = set()
    filtered = []
    for r in all_results:
        if r['url'] not in seen:
            filtered.append({
                "title": r.get("title", ""),
                "url": r['url'],
                "content": r.get("content", ""),
                "type": "뉴스" if "news" in r['url'] else ("블로그" if "blog" in r['url'] else "기타"),
            })
            seen.add(r['url'])
    return filtered[:max_results]
