"""
고객 저장소 (Customer Repository)

설계 의도:
  - CustomerRepository는 추상 인터페이스. 지금은 엑셀 구현(ExcelCustomerRepository)을
    쓰지만, 3주 후 Supabase로 갈아끼울 때 같은 인터페이스의 새 구현만 만들면 된다.
  - 동명이인 처리: 이름으로 검색하면 후보 '목록'을 돌려준다. 정확히 한 명을 특정하는
    건 customer_id로만 한다.
"""

from __future__ import annotations

import os
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from openpyxl import Workbook, load_workbook

from models import Customer, validate_birth_date, validate_name


# ---------------------------------------------------------------------------
# 추상 인터페이스
# ---------------------------------------------------------------------------

class CustomerRepository(ABC):
    """고객 저장소 인터페이스. 구현체는 엑셀/Supabase 등으로 교체 가능."""

    @abstractmethod
    def add_customer(self, name: str, birth_date: str, primary_pb: str) -> Customer:
        ...

    @abstractmethod
    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        ...

    @abstractmethod
    def find_by_name(self, name: str) -> list[Customer]:
        """이름이 일치하는 모든 고객(동명이인 포함)을 반환."""
        ...

    @abstractmethod
    def find_match(self, name: str, birth_date: str) -> list[Customer]:
        """이름+생년월일이 모두 일치하는 고객을 반환 (보통 0 또는 1명)."""
        ...

    @abstractmethod
    def list_all(self) -> list[Customer]:
        ...


# ---------------------------------------------------------------------------
# 동명이인 해소 결과
# ---------------------------------------------------------------------------

class ResolveResult:
    """
    이름으로 고객을 찾을 때 PB에게 돌려주는 결과.
      - NONE: 일치하는 고객 없음 -> 신규 등록 안내
      - SINGLE: 정확히 한 명 -> 바로 사용 가능
      - MULTIPLE: 동명이인 여럿 -> PB가 골라야 함 (candidates 제공)
    """
    NONE = "none"
    SINGLE = "single"
    MULTIPLE = "multiple"

    def __init__(self, kind: str, candidates: list[Customer]):
        self.kind = kind
        self.candidates = candidates

    def __repr__(self) -> str:
        labels = [c.display_label() for c in self.candidates]
        return f"<ResolveResult {self.kind}: {labels}>"


# ---------------------------------------------------------------------------
# 엑셀 구현
# ---------------------------------------------------------------------------

class ExcelCustomerRepository(CustomerRepository):
    """엑셀 파일을 단일 저장소로 쓰는 구현. Customers 시트를 사용."""

    SHEET = "Customers"
    HEADERS = ["customer_id", "name", "birth_date", "primary_pb", "registered_at"]

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(path):
            self._init_file()

    def _init_file(self) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = self.SHEET
        ws.append(self.HEADERS)
        wb.save(self.path)

    def _load_ws(self):
        wb = load_workbook(self.path)
        if self.SHEET not in wb.sheetnames:
            ws = wb.create_sheet(self.SHEET)
            ws.append(self.HEADERS)
        return wb, wb[self.SHEET]

    def _read_all_rows(self) -> list[dict]:
        wb, ws = self._load_ws()
        rows = []
        header = None
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                header = list(row)
                continue
            if row is None or all(c is None for c in row):
                continue
            rows.append(dict(zip(header, row)))
        return rows

    def _generate_id(self, existing_ids: set[str]) -> str:
        """C + 4자리 순번. 충돌 시 다음 번호로. 빈 저장소면 C0001부터."""
        max_num = 0
        for cid in existing_ids:
            if cid and cid.startswith("C") and cid[1:].isdigit():
                max_num = max(max_num, int(cid[1:]))
        candidate = f"C{max_num + 1:04d}"
        # 안전장치: 만에 하나 충돌하면 무작위 보정
        while candidate in existing_ids:
            candidate = f"C{random.randint(1, 9999):04d}"
        return candidate

    def add_customer(self, name: str, birth_date: str, primary_pb: str) -> Customer:
        name = validate_name(name)
        birth_date = validate_birth_date(birth_date)
        primary_pb = validate_name(primary_pb)

        existing = self._read_all_rows()
        existing_ids = {str(r["customer_id"]) for r in existing}
        new_id = self._generate_id(existing_ids)

        customer = Customer(
            customer_id=new_id,
            name=name,
            birth_date=birth_date,
            primary_pb=primary_pb,
            registered_at=datetime.now().isoformat(timespec="seconds"),
        )

        wb, ws = self._load_ws()
        ws.append([customer.customer_id, customer.name, customer.birth_date,
                   customer.primary_pb, customer.registered_at])
        wb.save(self.path)
        return customer

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        for r in self._read_all_rows():
            if str(r["customer_id"]) == customer_id:
                return Customer.from_row(r)
        return None

    def find_by_name(self, name: str) -> list[Customer]:
        name = name.strip()
        return [Customer.from_row(r) for r in self._read_all_rows()
                if str(r["name"]).strip() == name]

    def find_match(self, name: str, birth_date: str) -> list[Customer]:
        name = name.strip()
        birth_date = birth_date.strip()
        return [Customer.from_row(r) for r in self._read_all_rows()
                if str(r["name"]).strip() == name
                and str(r["birth_date"]).strip() == birth_date]

    def list_all(self) -> list[Customer]:
        return [Customer.from_row(r) for r in self._read_all_rows()]


# ---------------------------------------------------------------------------
# 고수준 흐름: 상담 입력 시 고객 특정 / 신규 등록 판단
# ---------------------------------------------------------------------------

def resolve_customer(repo: CustomerRepository, name: str) -> ResolveResult:
    """
    PB가 상담 입력 시 이름을 치면 호출.
    동명이인이 여럿이면 MULTIPLE로 후보를 돌려 PB가 고르게 한다.
    이것이 같은 사람이 여러 ID로 쪼개지는 사고를 막는 핵심 흐름.
    """
    matches = repo.find_by_name(name)
    if not matches:
        return ResolveResult(ResolveResult.NONE, [])
    if len(matches) == 1:
        return ResolveResult(ResolveResult.SINGLE, matches)
    return ResolveResult(ResolveResult.MULTIPLE, matches)
