"""
환경 변수를 관리하는 설정(Configuration) 모듈.
.env 파일이나 시스템 환경 변수에서 값을 자동으로 읽어옴.
"""

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    애플리케이션 환경 변수 설정을 관리하는 클래스.

    이 클래스는 .env 파일 또는 시스템 환경 변수에서
    각종 API 키, 서버 주소, JWT 시크릿, 모델명 등을 자동으로 읽어서
    서비스 전체에서 사용할 수 있도록 제공.
    """
    OPENAI_API_KEY: str
    MAIN_SERVER_URL: str = "http://localhost:8080"
    CHATBOT_SERVER_URL: str = "http://localhost:8001"
    JWT_SECRET: str
    JWT_ALGORITHM: str
    API_V1_STR: str = "/api/v1"
    OPENAI_API_BASE_URL: str
    OPENAI_MODEL: str = "gpt-4.1"
    GOOGLE_API_KEY: str
    GOOGLE_CSE_ID: str
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None

    class Config:
        """Pydantic-settings의 동작을 구성하는 내부 클래스."""
        env_file = ".env"
        env_file_encoding = 'utf-8'

# 설정 인스턴스를 생성하여 다른 모듈에서 가져다 쓸 수 있도록 함
settings = Settings()