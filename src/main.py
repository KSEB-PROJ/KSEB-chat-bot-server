"""
챗봇 서버의 메인 진입점(Entrypoint) 파일.
FastAPI 애플리케이션을 생성하고 라우터와 미들웨어를 설정.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routers import chatbot_router

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="KSEB AI Chatbot Server",
    description="협업 툴을 위한 AI 기능 제공 서버",
    version="1.0.0",
)

# CORS 미들웨어 설정 (모든 출처 허용 - 개발 환경)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# API 라우터 등록
app.include_router(chatbot_router.router)

@app.get("/")
async def read_root():
    """서버 헬스 체크를 위한 기본 엔드포인트."""
    return {"status": "AI Server is running"}
