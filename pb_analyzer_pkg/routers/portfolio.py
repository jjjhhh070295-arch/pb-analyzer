import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deps import get_session_repo, get_customer_repo
from optimizer import optimize, ASSETS, OptimizationResult
from tax_products import build_candidates, candidates_to_prompt_block

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


# ===========================================================================
# 절세 전략 (룰 기반 후보 + LLM 정성 코멘트)
# ===========================================================================

_TAX_STRATEGY_PROMPT = """\
너는 한국 증권사 PB를 돕는 절세 자문 보조다. 아래 고객 7요인 분석 결과와
검토 가능한 절세 상품 후보(룰 기반)를 보고, 우선순위와 이유·주의사항을 정리하라.

반드시 지켜라:
- 자문이 아닌 "검토 권고" 톤. "~합니다" 단정 금지, "~ 검토를 권합니다" 형식.
- 출력은 지정한 JSON만. 코드펜스·설명 금지.
- 한 상품에 대해 priority는 high/medium/low 중 하나.
- caveats는 PB가 반드시 확인해야 할 가정·제한사항.

[출력 JSON 스키마]
{
  "strategy_summary": "전체 절세 전략 한 문단(2~3줄). 고객 상황 핵심 요약 + 우선 검토 방향.",
  "ranked": [
    {
      "product_id": "isa|pension_savings|irp|tax_free_savings",
      "priority": "high|medium|low",
      "reason": "왜 이 우선순위인지(고객 상황 기반)",
      "caveats": "PB가 확인할 점·가정"
    }
  ]
}
"""


class TaxStrategyOut(BaseModel):
    candidates: list[dict]
    summary: str
    ranked: list[dict]


def _pick_demo_tax_strategy(raw_text: str) -> dict:
    """API 키 없을 때 시나리오별 더미 전략."""
    t = raw_text or ""
    if any(k in t for k in ("법인", "가업승계", "잉여")):
        return {
            "strategy_summary": "법인 잉여자금·가업승계 단계 — 개인 ISA·연금저축은 제한적, "
                "법인 명의 분리과세 상품과 가업상속공제·증여공제 사전 설계를 우선 검토 권고.",
            "ranked": [
                {"product_id": "irp", "priority": "medium",
                 "reason": "대표 개인 소득에 대한 세액공제 활용으로 한계세율 효과적.",
                 "caveats": "55세 이전 인출 제한, 안전자산 30% 의무. 대표 본인 노후 자금 분리 가정 시 적합."},
                {"product_id": "pension_savings", "priority": "medium",
                 "reason": "IRP와 합산 900만원 한도 활용.",
                 "caveats": "중도해지 시 16.5% 기타소득세."},
                {"product_id": "isa", "priority": "low",
                 "reason": "법인 명의 운용이 핵심이라 개인 ISA 우선순위는 후순위.",
                 "caveats": "직전 3년 금융소득종합과세 이력 시 가입 제한."},
                {"product_id": "tax_free_savings", "priority": "low",
                 "reason": "대표 연령에 따라 검토.",
                 "caveats": "65세 이상 또는 장애인 등 적격 조건 확인."},
            ],
        }
    if any(k in t for k in ("부동산", "임대", "보유세", "종부세")):
        return {
            "strategy_summary": "부동산 비중 80%·종부세 부담 — 일부 처분 후 ISA·비과세종합저축으로 "
                "이전, 자녀 증여 분산과 병행해 보유세 및 양도세 부담 완화 검토 권고.",
            "ranked": [
                {"product_id": "isa", "priority": "high",
                 "reason": "부동산 일부 처분 자금의 비과세·분리과세 이전처로 효과적.",
                 "caveats": "직전 3년 금융소득종합과세 이력 시 가입 제한, 의무가입 3년."},
                {"product_id": "tax_free_savings", "priority": "high",
                 "reason": "60대 → 65세 도달 시 한도 5천만원 비과세 적극 활용.",
                 "caveats": "정확한 연령·장애인 등록 등 PB 확인 필요."},
                {"product_id": "pension_savings", "priority": "medium",
                 "reason": "임대수익 일부에 대한 세액공제 활용 가능.",
                 "caveats": "노후 현금흐름 설계와 함께 검토."},
                {"product_id": "irp", "priority": "low",
                 "reason": "근로·사업소득 비중이 낮을 가능성.",
                 "caveats": "임대소득의 사업소득 분류 여부 확인 필요."},
            ],
        }
    if any(k in t for k in ("사업 매각", "현금성 자산", "예금", "MMF", "인플레이션")):
        return {
            "strategy_summary": "수십억 현금 + 종합과세 진입 우려 — ISA·연금저축·IRP 한도 최대 활용 후 "
                "분리과세 채권형 펀드와 배우자 명의 분산으로 금융소득 누진을 분산 검토 권고.",
            "ranked": [
                {"product_id": "isa", "priority": "high",
                 "reason": "원금 손실 거부감 + 분리과세 9.9%로 종합과세 회피 효과 큼.",
                 "caveats": "연 납입 2천만원·총 1억 한도. 직전 3년 종합과세 이력 시 가입 제한."},
                {"product_id": "pension_savings", "priority": "high",
                 "reason": "세액공제 한도 즉시 활용 가능, 연금 수령 시 저율 분리과세.",
                 "caveats": "장기 보유 전제 — 단기 유동성 필요 시 부적합."},
                {"product_id": "irp", "priority": "high",
                 "reason": "연금저축과 합산 900만원까지 세액공제 추가 활용.",
                 "caveats": "안전자산 30% 의무, 55세 이전 인출 제한."},
                {"product_id": "tax_free_savings", "priority": "medium",
                 "reason": "연령 도달 시 5천만원 비과세 한도 확보 권고.",
                 "caveats": "현재 적격 여부 PB 확인 필요."},
            ],
        }
    # 기본
    return {
        "strategy_summary": "일반 자산가 — 연금저축·IRP 세액공제 한도 활용을 1순위로, "
            "ISA로 변동성 자산의 분리과세 효과를 확보하는 단계적 접근 권고.",
        "ranked": [
            {"product_id": "pension_savings", "priority": "high",
             "reason": "세액공제 한도 600만원 즉시 확보.",
             "caveats": "중도해지 시 16.5% 기타소득세."},
            {"product_id": "irp", "priority": "high",
             "reason": "연금저축과 합산 900만원 세액공제.",
             "caveats": "안전자산 30% 의무."},
            {"product_id": "isa", "priority": "medium",
             "reason": "ETF 운용분에 대해 비과세·분리과세 효과.",
             "caveats": "의무가입 3년, 연 납입 한도 2천만원."},
            {"product_id": "tax_free_savings", "priority": "low",
             "reason": "65세 이상 적격 시 검토.",
             "caveats": "현재 적격 여부 PB 확인 필요."},
        ],
    }


@router.post("/sessions/{session_id}/tax-strategy")
def tax_strategy(session_id: str):
    """7요인 분석 기반 절세 상품 후보·우선순위·코멘트를 반환."""
    repo = get_session_repo()
    sess = repo.get(session_id)
    if not sess:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    # 고객 생년월일(비과세종합저축 자격 판정용)
    cust = get_customer_repo().get_by_id(sess.customer_id)
    birth_date = cust.birth_date if cust else None

    # 1) 룰 기반 후보 생성
    cands = build_candidates(sess.result, customer_birth_date=birth_date)

    # 2) LLM에 정성 코멘트 요청 (또는 mock)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        from llm_client import AnthropicLLMClient, extract_json
        block = candidates_to_prompt_block(cands)
        user_msg = (
            f"[고객 7요인 분석 요약]\n"
            f"- 목표수익률: {sess.result.goal_return.return_min} ~ {sess.result.goal_return.return_max}\n"
            f"- 위험허용도 binding: {sess.result.risk_tolerance.binding}\n"
            f"- 투자기간: {sess.result.horizon.years}년\n"
            f"- 연 금융소득: {sess.result.tax.annual_financial_income}\n"
            f"- 세무 항목: {sess.result.tax.items}\n"
            f"- 법적 제약: {sess.result.legal.items}\n"
            f"- 고유 상황: {sess.result.unique.notes}\n\n"
            f"[검토 가능한 절세 상품 후보]\n{block}\n"
        )
        try:
            raw = AnthropicLLMClient(api_key=api_key).complete(_TAX_STRATEGY_PROMPT, user_msg)
            llm_out = extract_json(raw)
        except Exception:
            llm_out = _pick_demo_tax_strategy(sess.raw_text)
    else:
        llm_out = _pick_demo_tax_strategy(sess.raw_text)

    return {
        "candidates": [
            {
                "product_id": c.product_id,
                "name": c.name,
                "one_liner": c.one_liner,
                "limit_text": c.limit_text,
                "eligible": c.eligible,
                "eligibility_note": c.eligibility_note,
                "estimated_saving_won": c.estimated_saving_won,
                "saving_basis": c.saving_basis,
            }
            for c in cands
        ],
        "summary": llm_out.get("strategy_summary", ""),
        "ranked": llm_out.get("ranked", []),
    }


class ConfirmTaxStrategyIn(BaseModel):
    candidates: list[dict]
    summary: str
    ranked: list[dict]
    note: Optional[str] = None    # PB 추가 코멘트(고객 화면 노출)


@router.put("/sessions/{session_id}/tax-strategy/confirm")
def confirm_tax_strategy(session_id: str, body: ConfirmTaxStrategyIn):
    """PB가 검토한 절세 전략을 확정해 고객 화면에 송출."""
    repo = get_session_repo()
    sess = repo.get(session_id)
    if not sess:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    sess.result.confirmed_tax_strategy = {
        "candidates": body.candidates,
        "summary": body.summary,
        "ranked": body.ranked,
        "note": body.note,
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
    }
    repo.update_result(session_id, sess.result)
    return sess.result.confirmed_tax_strategy


@router.delete("/sessions/{session_id}/tax-strategy/confirm", status_code=204)
def clear_tax_strategy(session_id: str):
    """확정된 절세 전략을 해제(고객 화면에서 사라짐)."""
    repo = get_session_repo()
    sess = repo.get(session_id)
    if not sess:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    sess.result.confirmed_tax_strategy = None
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
