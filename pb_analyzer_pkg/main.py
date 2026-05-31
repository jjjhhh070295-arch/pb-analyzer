from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import customers, sessions, portfolio

app = FastAPI(title="PB 고객 분석 시스템", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프론트 도메인 확정 후 제한
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
