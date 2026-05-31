"""
저장소 팩토리.

SUPABASE_URL 환경변수가 있으면 Supabase, 없으면 Excel(로컬 개발용)을 사용한다.
routers가 여기서만 import하면 백엔드 교체가 이 파일 한 곳에서 끝난다.
"""

import os

from customer_repository import CustomerRepository, ExcelCustomerRepository
from session_repository import SessionRepository, ExcelSessionRepository

EXCEL_PATH = os.getenv("EXCEL_PATH", "data.xlsx")


def get_customer_repo() -> CustomerRepository:
    if os.getenv("SUPABASE_URL"):
        from supabase_repositories import SupabaseCustomerRepository
        return SupabaseCustomerRepository()
    return ExcelCustomerRepository(EXCEL_PATH)


def get_session_repo() -> SessionRepository:
    if os.getenv("SUPABASE_URL"):
        from supabase_repositories import SupabaseSessionRepository
        return SupabaseSessionRepository()
    return ExcelSessionRepository(EXCEL_PATH)
