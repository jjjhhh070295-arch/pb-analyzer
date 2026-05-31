from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import customers, sessions, portfolio

app = FastAPI(title="PB 고객 분석 시스템", version="1.0.0")

# CORS: 프로덕션 도메인 + 로컬 개발만 허용.
# Vercel 미리보기 도메인(*.vercel.app)은 정규식으로 매칭.
_ALLOWED_ORIGINS = [
    "https://pb-analyzer.vercel.app",
    "http://localhost:3000",
    "http://localhost:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://pb-analyzer-.*\.vercel\.app",  # PR 미리보기
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
