"""
챗봇 API의 요청(Request) 및 응답(Response) 데이터 형식을 정의하는 스키마 모듈.
Pydantic BaseModel을 사용하여 데이터 유효성 검사를 수행.
"""

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """
    사용자 질문(query)을 담는 요청 스키마.
    """
    query: str = Field(
        description="사용자가 AI에게 보내는 질문 내용",
        example="어제 오후 회의 내용 요약해줘"
    )

class ChatResponse(BaseModel):
    """
    AI의 답변(answer)을 담는 응답 스키마.
    """
    answer: str = Field(
        description="AI의 답변 내용",
        example="오늘 오후 2시에 팀 회의 일정을 생성했습니다."
    )
    