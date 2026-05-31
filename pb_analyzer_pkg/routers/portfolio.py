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


@router.get("/universe")
def get_universe():
    """투자 가능한 자산 유니버스 목록."""
    return [
        {"asset_id": aid, "ticker": meta["ticker"],
         "name": meta["name"], "category": meta["category"]}
        for aid, meta in ASSETS.items()
    ]
