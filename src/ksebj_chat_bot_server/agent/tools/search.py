"""
웹 검색 요약 툴.
"""

from langchain.tools import tool


@tool
def web_search(query: str) -> str:
    """간단한 웹 검색 요약(추후 실제 API 연동)."""
    return f"'{query}' 검색 결과 요약(예시)"
