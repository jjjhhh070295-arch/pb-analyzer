import os
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from analyzer import analyze
from validators import validate
from models import SessionStatus
from mock_llm import MockLLMClient
from deps import get_customer_repo as _customer_repo, get_session_repo as _session_repo

router = APIRouter(prefix="/sessions", tags=["sessions"])

# 분석 진행 상태 (서버 메모리). 추후 DB/Redis로 이전 가능.
_tasks: dict[str, dict] = {}


def _llm():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        from llm_client import AnthropicLLMClient
        return AnthropicLLMClient(api_key=api_key)
    return MockLLMClient()


class StartAnalysisIn(BaseModel):
    customer_id: str
    pb_name: str
    raw_text: str
    consult_date: Optional[str] = None


def _session_to_dict(s) -> dict:
    return {
        "session_id": s.session_id,
        "customer_id": s.customer_id,
        "customer_name": s.customer_name,
        "pb_name": s.pb_name,
        "consult_date": s.consult_date,
        "consult_datetime": s.consult_datetime,
        "status": s.status,
        "raw_text": s.raw_text,
        "result": s.result.to_dict(),
        "summary": s.summary(),
    }


def _do_analysis(session_id: str, customer_id: str, customer_name: str,
                 pb_name: str, raw_text: str, consult_date: Optional[str]):
    try:
        report = analyze(raw_text, _llm())
        result = validate(report.result, raw_text)
        _session_repo().save(
            customer_id=customer_id,
            customer_name=customer_name,
            pb_name=pb_name,
            raw_text=raw_text,
            result=result,
            consult_date=consult_date,
            session_id=session_id,
        )
        _tasks[session_id]["status"] = "done"
    except Exception as e:
        _tasks[session_id]["status"] = "error"
        _tasks[session_id]["error"] = str(e)


@router.post("", status_code=202)
def start_analysis(body: StartAnalysisIn, background_tasks: BackgroundTasks):
    customer = _customer_repo().get_by_id(body.customer_id)
    if not customer:
        raise HTTPException(404, "고객을 찾을 수 없습니다.")

    session_id = _session_repo().next_id()
    _tasks[session_id] = {"status": "analyzing", "error": None}

    background_tasks.add_task(
        _do_analysis,
        session_id=session_id,
        customer_id=body.customer_id,
        customer_name=customer.name,
        pb_name=body.pb_name,
        raw_text=body.raw_text,
        consult_date=body.consult_date,
    )
    return {"session_id": session_id, "status": "analyzing"}


@router.get("/{session_id}/status")
def get_status(session_id: str):
    if session_id in _tasks:
        return {"session_id": session_id, **_tasks[session_id]}
    s = _session_repo().get(session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    return {"session_id": session_id, "status": "done", "error": None}


@router.get("")
def list_sessions(
    customer_id: Optional[str] = Query(None),
    pb_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    sessions = _session_repo().list_filtered(
        pb_name=pb_name, date_from=date_from, date_to=date_to, status=status
    )
    if customer_id:
        sessions = [s for s in sessions if s.customer_id == customer_id]
    return [_session_to_dict(s) for s in sessions]


@router.get("/{session_id}")
def get_session(session_id: str):
    task = _tasks.get(session_id)
    if task:
        if task["status"] == "analyzing":
            return {"session_id": session_id, "status": "analyzing"}
        if task["status"] == "error":
            raise HTTPException(500, task.get("error", "분석 중 오류 발생"))
    s = _session_repo().get(session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    return _session_to_dict(s)


@router.patch("/{session_id}/confirm")
def confirm_session(session_id: str):
    try:
        _session_repo().update_status(session_id, SessionStatus.CONFIRMED.value)
        return {"session_id": session_id, "status": SessionStatus.CONFIRMED.value}
    except KeyError:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")


@router.patch("/{session_id}/flags/{rule_id}/resolve")
def resolve_flag(session_id: str, rule_id: str):
    repo = _session_repo()
    s = repo.get(session_id)
    if not s:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    matched = any(f for f in s.result.flags if f.rule_id == rule_id)
    if not matched:
        raise HTTPException(404, f"플래그를 찾을 수 없습니다: {rule_id}")
    for f in s.result.flags:
        if f.rule_id == rule_id:
            f.resolved = True
    repo.update_result(session_id, s.result)
    return {"session_id": session_id, "rule_id": rule_id, "resolved": True}
