"""
Supabase 저장소 구현체.

ExcelCustomerRepository / ExcelSessionRepository와 동일한 추상 인터페이스를 구현한다.
환경변수 SUPABASE_URL + SUPABASE_SERVICE_KEY 가 설정돼 있을 때만 사용된다.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime
from typing import Optional

from supabase import create_client, Client

from models import Customer, validate_birth_date, validate_name, SessionStatus
from customer_repository import CustomerRepository, ResolveResult
from session_repository import SessionRepository, Session
from analysis_schema import AnalysisResult


def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            f"[SUPABASE-DEBUG] env vars missing: URL={'OK' if url else 'EMPTY'}, "
            f"KEY={'OK' if key else 'EMPTY'}"
        )
    try:
        return create_client(url, key)
    except Exception as e:
        raise RuntimeError(
            f"[SUPABASE-DEBUG] create_client failed: {type(e).__name__}: {e}. "
            f"URL prefix='{url[:40]}', KEY length={len(key)}, KEY prefix='{key[:20]}'"
        ) from e


# ---------------------------------------------------------------------------
# 고객 저장소
# ---------------------------------------------------------------------------

class SupabaseCustomerRepository(CustomerRepository):

    def __init__(self):
        self._c = _client()

    def _gen_id(self, existing: set[str]) -> str:
        max_num = 0
        for cid in existing:
            if cid and cid.startswith("C") and cid[1:].isdigit():
                max_num = max(max_num, int(cid[1:]))
        candidate = f"C{max_num + 1:04d}"
        while candidate in existing:
            candidate = f"C{random.randint(1, 9999):04d}"
        return candidate

    def add_customer(self, name: str, birth_date: str, primary_pb: str) -> Customer:
        name = validate_name(name)
        birth_date = validate_birth_date(birth_date)
        primary_pb = validate_name(primary_pb)

        existing = {r["customer_id"] for r in
                    self._c.table("customers").select("customer_id").execute().data}
        new_id = self._gen_id(existing)

        customer = Customer(
            customer_id=new_id,
            name=name,
            birth_date=birth_date,
            primary_pb=primary_pb,
            registered_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._c.table("customers").insert({
            "customer_id": customer.customer_id,
            "name": customer.name,
            "birth_date": customer.birth_date,
            "primary_pb": customer.primary_pb,
            "registered_at": customer.registered_at,
        }).execute()
        return customer

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        resp = self._c.table("customers").select("*").eq("customer_id", customer_id).execute()
        return Customer.from_row(resp.data[0]) if resp.data else None

    def find_by_name(self, name: str) -> list[Customer]:
        resp = self._c.table("customers").select("*").eq("name", name.strip()).execute()
        return [Customer.from_row(r) for r in resp.data]

    def find_match(self, name: str, birth_date: str) -> list[Customer]:
        resp = (self._c.table("customers").select("*")
                .eq("name", name.strip()).eq("birth_date", birth_date.strip()).execute())
        return [Customer.from_row(r) for r in resp.data]

    def list_all(self) -> list[Customer]:
        resp = self._c.table("customers").select("*").order("registered_at").execute()
        return [Customer.from_row(r) for r in resp.data]

    def delete(self, customer_id: str) -> None:
        resp = (self._c.table("customers").delete()
                .eq("customer_id", customer_id).execute())
        if not resp.data:
            raise KeyError(f"고객을 찾을 수 없습니다: {customer_id}")


# ---------------------------------------------------------------------------
# 세션 저장소
# ---------------------------------------------------------------------------

class SupabaseSessionRepository(SessionRepository):

    def __init__(self):
        self._c = _client()

    def _gen_id(self, existing: set[str]) -> str:
        n = 0
        for s in existing:
            if s and s.startswith("S") and s[1:].isdigit():
                n = max(n, int(s[1:]))
        cand = f"S{n+1:05d}"
        while cand in existing:
            cand = f"S{random.randint(1, 99999):05d}"
        return cand

    def next_id(self) -> str:
        resp = self._c.table("sessions").select("session_id").execute()
        return self._gen_id({r["session_id"] for r in resp.data})

    def _row_to_session(self, d: dict) -> Session:
        result = AnalysisResult.from_dict(json.loads(d["result_json"]))
        return Session(
            session_id=str(d["session_id"]),
            customer_id=str(d["customer_id"]),
            customer_name=str(d["customer_name"]),
            pb_name=str(d["pb_name"]),
            consult_date=str(d["consult_date"]),
            consult_datetime=str(d["consult_datetime"]),
            status=str(d["status"]),
            raw_text=str(d.get("raw_text") or ""),
            result=result,
        )

    def _summary_cols(self, result: AnalysisResult) -> dict:
        gr = ""
        if result.goal_return.return_min is not None:
            lo = result.goal_return.return_min * 100
            hi = (result.goal_return.return_max or result.goal_return.return_min) * 100
            gr = f"{lo:.0f}~{hi:.0f}%" if hi != lo else f"{lo:.0f}%"
        risk = ""
        b = result.risk_tolerance.binding
        if b == "willingness":
            risk = result.risk_tolerance.willingness.level or ""
        elif b == "capacity":
            risk = result.risk_tolerance.capacity.level or ""
        return {
            "goal_return_summary": gr,
            "risk_level": risk,
            "horizon_years": result.horizon.years,
            "unresolved_flags": sum(1 for f in result.flags if not f.resolved),
            "follow_up_count": len(result.follow_up_questions),
        }

    def save(self, customer_id, customer_name, pb_name, raw_text, result,
             consult_date=None, status=SessionStatus.DRAFT.value,
             session_id: Optional[str] = None) -> Session:
        now = datetime.now()
        sid = session_id or self.next_id()
        sess = Session(
            session_id=sid,
            customer_id=customer_id,
            customer_name=customer_name,
            pb_name=pb_name,
            consult_date=consult_date or now.strftime("%Y-%m-%d"),
            consult_datetime=now.isoformat(timespec="seconds"),
            status=status,
            raw_text=raw_text,
            result=result,
        )
        self._c.table("sessions").insert({
            "session_id": sid,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "pb_name": pb_name,
            "consult_date": sess.consult_date,
            "consult_datetime": sess.consult_datetime,
            "status": status,
            "raw_text": raw_text,
            "result_json": json.dumps(result.to_dict(), ensure_ascii=False),
            **self._summary_cols(result),
        }).execute()
        return sess

    def get(self, session_id: str) -> Optional[Session]:
        resp = self._c.table("sessions").select("*").eq("session_id", session_id).execute()
        return self._row_to_session(resp.data[0]) if resp.data else None

    def update_status(self, session_id: str, status: str) -> None:
        resp = (self._c.table("sessions").update({"status": status})
                .eq("session_id", session_id).execute())
        if not resp.data:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")

    def update_result(self, session_id: str, result: AnalysisResult,
                      raw_text: Optional[str] = None,
                      status: Optional[str] = None) -> None:
        payload = {"result_json": json.dumps(result.to_dict(), ensure_ascii=False),
                   **self._summary_cols(result)}
        if raw_text is not None:
            payload["raw_text"] = raw_text
        if status is not None:
            payload["status"] = status
        resp = (self._c.table("sessions").update(payload)
                .eq("session_id", session_id).execute())
        if not resp.data:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")

    def delete(self, session_id: str) -> None:
        resp = (self._c.table("sessions").delete()
                .eq("session_id", session_id).execute())
        if not resp.data:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")

    def list_by_customer(self, customer_id: str) -> list[Session]:
        resp = (self._c.table("sessions").select("*")
                .eq("customer_id", customer_id).order("consult_datetime").execute())
        return [self._row_to_session(r) for r in resp.data]

    def list_filtered(self, pb_name=None, date_from=None, date_to=None, status=None) -> list[Session]:
        q = self._c.table("sessions").select("*").order("consult_datetime", desc=True)
        if pb_name:
            q = q.eq("pb_name", pb_name)
        if date_from:
            q = q.gte("consult_date", date_from)
        if date_to:
            q = q.lte("consult_date", date_to)
        if status:
            q = q.eq("status", status)
        return [self._row_to_session(r) for r in q.execute().data]
