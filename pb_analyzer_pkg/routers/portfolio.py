from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deps import get_session_repo
from optimizer import optimize, ASSETS, OptimizationResult

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class OptimizeRequest(BaseModel):
    session_id: str
    years: int = 3        # 데이터 수집 기간 (년)


def _result_to_dict(r: OptimizationResult) -> dict:
    return {
        "weights": [
            {
                "asset_id": aid,
                "name": r.asset_names.get(aid, aid),
                "category": ASSETS[aid]["category"],
                "weight": round(w, 4),
                "weight_pct": round(w * 100, 2),
            }
            for aid, w in sorted(r.weights.items(), key=lambda x: -x[1])
        ],
        "metrics": {
            "expected_return": round(r.expected_return, 4),
            "expected_return_pct": round(r.expected_return * 100, 2),
            "downside_volatility": round(r.downside_volatility, 4),
            "downside_volatility_pct": round(r.downside_volatility * 100, 2),
            "downside_risk_score": round(r.downside_risk_score, 1),   # 0~100
            "sortino_ratio": round(r.sortino_ratio, 3),
            "beta": round(r.beta, 3),
        },
        "provisional": r.provisional,
        "warnings": r.warnings,
    }


@router.post("/optimize")
def run_optimize(body: OptimizeRequest):
    """확정 세션의 7요인 제약을 바탕으로 리스크 패리티 포트폴리오를 최적화합니다."""
    repo = get_session_repo()
    session = repo.get(body.session_id)
    if not session:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    if session.status != "확정":
        raise HTTPException(400, "확정된 세션에서만 포트폴리오 최적화를 실행할 수 있습니다.")

    oc = session.result.optimizer_constraints
    try:
        result = optimize(
            risk_level=oc.risk_level,
            excluded_sectors=oc.excluded_sectors,
            target_return_min=oc.target_return_min,
            target_return_max=oc.target_return_max,
            provisional=oc.provisional,
            years=body.years,
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return _result_to_dict(result)


class PortfolioWeightIn(BaseModel):
    asset_id: str
    name: str
    category: str
    weight_pct: float           # 0~100


class ConfirmPortfolioIn(BaseModel):
    weights: list[PortfolioWeightIn]
    note: Optional[str] = None     # PB 메모(고객 화면에도 노출)
    metrics: Optional[dict] = None # 화면 표시용 지표(고객 화면엔 안 보임)


@router.put("/sessions/{session_id}/confirm")
def confirm_portfolio(session_id: str, body: ConfirmPortfolioIn):
    """PB가 임의로 수정한 포트폴리오를 확정 저장. result.confirmed_portfolio에 들어가 고객 화면에 송출됨."""
    repo = get_session_repo()
    sess = repo.get(session_id)
    if not sess:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    total = sum(w.weight_pct for w in body.weights)
    if abs(total - 100.0) > 0.5:
        raise HTTPException(400, f"비중 합계가 100%여야 합니다 (현재 {total:.1f}%).")

    weights = [
        {"asset_id": w.asset_id, "name": w.name, "category": w.category,
         "weight": round(w.weight_pct / 100, 4), "weight_pct": round(w.weight_pct, 2)}
        for w in body.weights if w.weight_pct > 0
    ]

    sess.result.confirmed_portfolio = {
        "weights": weights,
        "note": body.note,
        "metrics": body.metrics,
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
    }
    repo.update_result(session_id, sess.result)
    return sess.result.confirmed_portfolio


@router.delete("/sessions/{session_id}/confirm", status_code=204)
def clear_portfolio(session_id: str):
    """확정 포트폴리오 제거(고객 화면에서 사라짐)."""
    repo = get_session_repo()
    sess = repo.get(session_id)
    if not sess:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    sess.result.confirmed_portfolio = None
    repo.update_result(session_id, sess.result)
    return None


@router.get("/universe")
def get_universe():
    """투자 가능한 자산 유니버스 목록."""
    return [
        {"asset_id": aid, "ticker": meta["ticker"],
         "name": meta["name"], "category": meta["category"]}
        for aid, meta in ASSETS.items()
    ]
