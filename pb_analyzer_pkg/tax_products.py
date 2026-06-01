"""
절세 상품 카탈로그 + 룰 기반 필터링·절감액 추정 (한국 2026 기준).

설계:
  - 4개 핵심 상품(ISA / 연금저축 / IRP / 비과세 종합저축)
  - 각 상품마다 is_eligible(분석결과) / estimate_savings(분석결과)
  - 결과는 LLM이 정성적 코멘트를 얹어 최종 우선순위·이유로 정리
  - 자문 책임 회피: 모두 "검토 권고" 톤. 단정 표현 금지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from analysis_schema import AnalysisResult
import rules_config as cfg


@dataclass
class ProductCandidate:
    product_id: str                  # "isa" | "pension_savings" | "irp" | "tax_free_savings"
    name: str
    one_liner: str                   # 짧은 설명 (고객 화면용도 가능)
    limit_text: str                  # 한도 표시 ("연 600만원 세액공제" 등)
    eligible: bool                   # 자격 충족 여부
    eligibility_note: str            # 자격에 대한 짧은 메모
    estimated_saving_won: Optional[int]  # 연 예상 절감액 (원)
    saving_basis: str                # 추정 근거


# ---------------------------------------------------------------------------
# 1. ISA
# ---------------------------------------------------------------------------

def _candidate_isa(r: AnalysisResult) -> ProductCandidate:
    annual_income = r.tax.annual_financial_income or 0
    # 200만원 비과세 + 초과분 9.9% 분리과세 → 종합과세(15.4%~46.2%) 회피
    # 보수적으로 24% 구간 가정해 비교
    assumed_marginal = 0.24
    if annual_income > cfg.FINANCIAL_INCOME_THRESHOLD:
        # 종합과세 대상이면 절감 효과 큼
        covered = min(annual_income, cfg.ISA_ANNUAL_DEPOSIT_LIMIT)
        saving = int(covered * (assumed_marginal - cfg.ISA_LOW_TAX_RATE))
        basis = f"종합과세 대상 → ISA로 옮기면 한계세율 ~24%(가정) 대신 9.9% 분리과세, " \
                f"또는 200만원까지 비과세. {covered:,.0f}원 기준 추정."
    else:
        saving = int(cfg.ISA_TAX_FREE_LIMIT * 0.154)  # 비과세 200만 × 일반세율 15.4%
        basis = f"비과세 한도 {cfg.ISA_TAX_FREE_LIMIT:,}원에 대해 15.4% 세금 회피 가정."

    return ProductCandidate(
        product_id="isa",
        name="ISA (개인종합자산관리계좌)",
        one_liner="비과세·분리과세 통합 절세 계좌, 손익 통산 가능.",
        limit_text=f"비과세 {cfg.ISA_TAX_FREE_LIMIT:,}원 + 초과분 {cfg.ISA_LOW_TAX_RATE*100:.1f}% 분리과세 / 연 납입 {cfg.ISA_ANNUAL_DEPOSIT_LIMIT:,}원",
        eligible=True,
        eligibility_note="만 19세 이상 거주자 누구나(직전 3년 금융소득 종합과세자 제외).",
        estimated_saving_won=saving,
        saving_basis=basis,
    )


# ---------------------------------------------------------------------------
# 2. 연금저축
# ---------------------------------------------------------------------------

def _candidate_pension_savings(r: AnalysisResult) -> ProductCandidate:
    # 한계세율 가정: 금융소득 종합과세 대상이면 16.5%, 아니면 13.2%로 보수적
    annual_income = r.tax.annual_financial_income or 0
    rate = cfg.PENSION_DEDUCT_RATE_LOW if annual_income > cfg.FINANCIAL_INCOME_THRESHOLD else cfg.PENSION_DEDUCT_RATE_HIGH
    saving = int(cfg.PENSION_SAVINGS_LIMIT * rate)

    return ProductCandidate(
        product_id="pension_savings",
        name="연금저축",
        one_liner="세액공제 + 연금 수령 시 저율 분리과세(3.3~5.5%).",
        limit_text=f"연 {cfg.PENSION_SAVINGS_LIMIT:,}원 세액공제 ({rate*100:.1f}%)",
        eligible=True,
        eligibility_note="거주자 누구나. 중도해지 시 16.5% 기타소득세 부과 — 장기 보유 전제.",
        estimated_saving_won=saving,
        saving_basis=f"한도 {cfg.PENSION_SAVINGS_LIMIT:,}원 × 공제율 {rate*100:.1f}% = {saving:,}원/년.",
    )


# ---------------------------------------------------------------------------
# 3. IRP
# ---------------------------------------------------------------------------

def _candidate_irp(r: AnalysisResult) -> ProductCandidate:
    annual_income = r.tax.annual_financial_income or 0
    rate = cfg.PENSION_DEDUCT_RATE_LOW if annual_income > cfg.FINANCIAL_INCOME_THRESHOLD else cfg.PENSION_DEDUCT_RATE_HIGH
    saving = int(cfg.IRP_EXTRA_LIMIT * rate)

    return ProductCandidate(
        product_id="irp",
        name="IRP (개인형 퇴직연금)",
        one_liner="연금저축과 합산 900만원까지 세액공제, 안전자산 30% 의무.",
        limit_text=f"연금저축 합산 {cfg.PENSION_TOTAL_LIMIT_W_IRP:,}원까지 ({rate*100:.1f}% 공제)",
        eligible=True,
        eligibility_note="소득(근로/사업/연금)이 있는 자. 55세 이전 인출 제한.",
        estimated_saving_won=saving,
        saving_basis=f"IRP 추가 한도 {cfg.IRP_EXTRA_LIMIT:,}원 × 공제율 {rate*100:.1f}% = {saving:,}원/년.",
    )


# ---------------------------------------------------------------------------
# 4. 비과세 종합저축
# ---------------------------------------------------------------------------

def _candidate_tax_free_savings(r: AnalysisResult, customer_birth_date: Optional[str] = None) -> ProductCandidate:
    """65세 이상 등 특정 대상만 적격. 분석 결과엔 나이가 없으므로 PB가 확인하도록 한다."""
    age = None
    if customer_birth_date:
        try:
            from datetime import date
            y, m, d = customer_birth_date.split("-")
            today = date.today()
            age = today.year - int(y) - ((today.month, today.day) < (int(m), int(d)))
        except Exception:
            age = None

    eligible = age is not None and age >= cfg.TAX_FREE_SAVINGS_MIN_AGE
    note = (
        f"고객 연령 {age}세 — 적격." if eligible else
        (f"고객 연령 {age}세 — 적격 연령({cfg.TAX_FREE_SAVINGS_MIN_AGE}세) 미달."
         if age is not None else
         f"적격 연령({cfg.TAX_FREE_SAVINGS_MIN_AGE}세 이상)·장애인 등록 여부 PB 확인 필요.")
    )

    # 절감 추정: 한도 5천만원 × 평균 이자율 3% × 15.4% 절감
    saving = int(cfg.TAX_FREE_SAVINGS_LIMIT * 0.03 * 0.154) if eligible else None
    basis = (f"한도 {cfg.TAX_FREE_SAVINGS_LIMIT:,}원의 연 이자 3% 가정 시 약 {saving:,}원/년 비과세."
             if eligible else "적격 시 한도 내 이자·배당 전액 비과세 (15.4% 회피).")

    return ProductCandidate(
        product_id="tax_free_savings",
        name="비과세 종합저축",
        one_liner="65세 이상·장애인 등 한정. 한도 내 이자·배당 전액 비과세.",
        limit_text=f"한도 {cfg.TAX_FREE_SAVINGS_LIMIT:,}원, 이자·배당 100% 비과세",
        eligible=eligible,
        eligibility_note=note,
        estimated_saving_won=saving,
        saving_basis=basis,
    )


# ---------------------------------------------------------------------------
# 외부 인터페이스
# ---------------------------------------------------------------------------

def build_candidates(result: AnalysisResult,
                     customer_birth_date: Optional[str] = None) -> list[ProductCandidate]:
    """7요인 결과 + 고객 정보로부터 4개 상품 후보를 생성."""
    return [
        _candidate_isa(result),
        _candidate_pension_savings(result),
        _candidate_irp(result),
        _candidate_tax_free_savings(result, customer_birth_date),
    ]


def candidates_to_prompt_block(cands: list[ProductCandidate]) -> str:
    """LLM에게 전달할 요약 블록."""
    lines = []
    for c in cands:
        lines.append(
            f"- [{c.product_id}] {c.name}\n"
            f"  한도: {c.limit_text}\n"
            f"  자격: {'적격' if c.eligible else '비적격/확인필요'} — {c.eligibility_note}\n"
            f"  예상 절감: {c.estimated_saving_won:,}원/년" if c.estimated_saving_won else
            f"  예상 절감: 추정 보류"
        )
    return "\n".join(lines)
