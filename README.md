<div align="center">
  
  ![header](https://capsule-render.vercel.app/api?type=waving&color=0:d5ccff,100:f4ffad&height=240&text=KSEB-AI%202팀%20'도와조'의%20Chatbot%20Repository&animation=fadeIn&fontColor=6a5858&fontSize=35&fontAlignY=40&desc=경기대학교%20SW%20Bootcamp%204기%20AI%20도메인%20Team%202&descAlignY=60)

</div>

---

## 🧑‍💻 About Us
> **안녕하세요!** 저희는 경기대학교 **SW Bootcamp 4기 AI 도메인 2팀 '도와조'** 입니다.  
> **AI 기술**을 활용해 **실제 문제를 해결하는 실용적인 프로젝트**를 만들고자 합니다. 🚀

---

## 🛠️ Tech Stacks

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=FastAPI&logoColor=white"/>
  <img src="https://img.shields.io/badge/LangChain-019934?style=for-the-badge&logo=LangChain&logoColor=white"/>
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=OpenAI&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=Docker&logoColor=white"/>
</p>

---

## 📂 About Our Project

> KSEB-Chatbot Repository는 **KSEB 4기 2팀의 AI 챗봇 서버 코드**를 담고 있습니다.  
> LangChain 기반의 AI 에이전트를 통해 사용자의 요청을 지능적으로 처리하고, 다양한 외부 도구와 연동하여 자동화된 작업을 수행합니다.

📌 **주요 기능:**
- 💬 자연어 이해(NLU)를 통한 사용자 의도 파악 및 대화 관리
- 🗓️ 백엔드 서버와 연동하여 팀 일정 조회, 생성, 수정, 삭제 기능 수행
- 📄 ArXiv, Semantic Scholar 등 학술 플랫폼 연동을 통한 논문 검색 및 요약
- 📊 웹 검색 기능 및 웹 페이지 내용 분석 및 요약
- 📝 검색된 정보를 바탕으로 PPT 및 보고서(DOCX) 자동 생성

---

## 🌳 Folder Structure
```text
KSEB-chat-bot-server
├── src
│   ├── agent           # LangChain 에이전트 및 도구(Tool) 정의
│   │   └── tools           # 스케줄, 웹 검색, 문서 생성 등 개별 기능 도구
│   ├── core            # 핵심 설정 (보안, 환경변수)
│   ├── routers         # API 엔드포인트 라우팅
│   ├── schemas         # Pydantic 데이터 모델 (요청/응답 DTO)
│   ├── services        # 핵심 비즈니스 로직
│   ├── templates       # 문서 생성에 사용되는 템플릿 파일
│   ├── utils           # 유틸리티 함수 (API 클라이언트 등)
│   └── main.py         # FastAPI 애플리케이션 진입점
├── .env                # 환경변수 설정 파일
├── pyproject.toml      # 프로젝트 의존성 및 메타데이터 관리
└── poetry.lock         # 의존성 버전 고정 파일
```

---

## 🚀 Our Goals  
✔️ **프로젝트팀을 위한 실용적인 협업 플랫폼 개발**  
✔️ **팀워크 기반의 프로젝트 완성 경험**  
✔️ **배운 기술을 실무와 연결**  

---

## 🤝 Team '도와조'

| Name | Role |
|------|------|
| 🧑‍🎓 안재현 | Project Manager & Backend Dev & Front Dev & Server Dev |
| 🧑‍🎓 황태연 | Backend Dev & AI Dev |
| 🧑‍🎓 이찬 | Backend Dev & AI Dev |
| 🧑‍🎓 김세현 | Front Dev |
| 🧑‍🎓 고윤서 | AI Dev |

---

<div align="center">

### 🌟 Thank you for visiting! 🌟  
⭐️ **저희의 Repo에 Star를 눌러주시면 큰 힘이 됩니다!** ⭐️  

![footer](https://capsule-render.vercel.app/api?type=waving&color=0:f4ffad,100:d5ccff&height=120&section=footer)

</div>

