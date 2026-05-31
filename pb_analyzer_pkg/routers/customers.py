from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from customer_repository import resolve_customer
from deps import get_customer_repo as _repo, get_session_repo as _session_repo

router = APIRouter(prefix="/customers", tags=["customers"])


class CreateCustomerIn(BaseModel):
    name: str
    birth_date: str
    primary_pb: str


@router.get("")
def list_customers():
    return [asdict(c) for c in _repo().list_all()]


@router.post("", status_code=201)
def create_customer(body: CreateCustomerIn):
    try:
        return asdict(_repo().add_customer(body.name, body.birth_date, body.primary_pb))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/search")
def search_customers(name: str = Query(..., min_length=1)):
    result = resolve_customer(_repo(), name)
    return {"kind": result.kind, "candidates": [asdict(c) for c in result.candidates]}


@router.get("/{customer_id}")
def get_customer(customer_id: str):
    c = _repo().get_by_id(customer_id)
    if not c:
        raise HTTPException(404, "고객을 찾을 수 없습니다.")
    return asdict(c)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: str):
    """고객을 완전히 삭제. 해당 고객의 모든 상담도 cascade로 함께 삭제한다."""
    customer_repo = _repo()
    if not customer_repo.get_by_id(customer_id):
        raise HTTPException(404, "고객을 찾을 수 없습니다.")

    # 1) 외래키 제약 회피: 세션을 먼저 모두 삭제
    session_repo = _session_repo()
    for s in session_repo.list_by_customer(customer_id):
        try:
            session_repo.delete(s.session_id)
        except KeyError:
            pass

    # 2) 고객 삭제
    customer_repo.delete(customer_id)
    return None
