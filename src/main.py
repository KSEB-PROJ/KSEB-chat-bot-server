"""
KSEB AI Chatbot Server 엔트리 포인트.
"""

from fastapi import FastAPI
from ksebj_chat_bot_server.routers.chatbot import router as chatbot_router

app = FastAPI(
    title="KSEB AI Chatbot Server",
    description="협업 툴을 위한 AI 기능 제공 서버",
    version="1.0.0",
)

app.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])


@app.get("/")
async def read_root():
    """Health check"""
    return {"status": "AI Server is running"}
