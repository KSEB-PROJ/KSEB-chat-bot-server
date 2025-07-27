"""
AI 서버의 환경 설정을 관리하는 모듈.
.env 파일로부터 JWT_SECRET, SPRING_BOOT_BASE_URL을 로드합니다.
"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """환경변수를 BaseSettings로 매핑하는 Pydantic 클래스."""

    JWT_SECRET: str
    SPRING_BOOT_BASE_URL: str

    class Config:
        """Pydantic 설정: .env 파일 경로 지정."""
        env_file = ".env"

# 전역으로 사용할 설정 인스턴스
settings = Settings()  # type: ignore
