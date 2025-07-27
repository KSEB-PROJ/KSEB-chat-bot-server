"""
챗봇 요청/응답 스키마 정의.
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
