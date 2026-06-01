"""
포트폴리오 최적화 엔진 (리스크 패리티)

설계:
  - 리스크 패리티: 각 자산이 포트폴리오 전체 위험에 동등하게 기여하도록 비중 결정.
    쏠림 없이 안정적. 입력 오차에 강건함.
  - 위험 축: 하방변동성(손실 구간만의 변동성) 연환산 → 0~100 스케일 변환.
  - 소르티노: 별도 "위험조정 성과 점수"로 표시 (위험 축과 분리).
  - excluded_sectors: 유니버스 내 해당 카테고리 ETF 제외.
  - risk_level: 자산별 비중 상한을 조정해 보수적/공격적 성향 반영.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# 자산 유니버스
# ---------------------------------------------------------------------------

ASSETS: dict[str, dict] = {
    "kodex200":  {"ticker": "069500.KS", "name": "KODEX 200 (국내주식)",    "category": "국내주식",   "sectors": []},
    "spy":       {"ticker": "SPY",        "name": "S&P 500 ETF (미국주식)",   "category": "해외주식",   "sectors": []},
    "qqq":       {"ticker": "QQQ",        "name": "나스닥 100 ETF",           "category": "해외주식",   "sectors": []},
    "vnq":       {"ticker": "VNQ",        "name": "미국 리츠 ETF",            "category": "리츠",       "sectors": []},
    "gld":       {"ticker": "GLD",        "name": "금 ETF",                   "category": "원자재",     "sectors": []},
    "slv":       {"ticker": "SLV",        "name": "은 ETF",                   "category": "원자재",     "sectors": []},
    "copx":      {"ticker": "COPX",       "name": "구리 광산 ETF",            "category": "원자재",     "sectors": []},
    "uup":       {"ticker": "UUP",        "name": "달러 인덱스 ETF",          "category": "달러",       "sectors": []},
}

# sector 키워드 → 해당 카테고리 제외
SECTOR_EXCLUSION: dict[str, list[str]] = {
    "tobacco":   [],       # 현재 유니버스에 담배 ETF 없음
    "gambling":  [],
    "alcohol":   [],
    "weapons":   [],
    "fossil":    [],
    "gaming":    [],
}

# 시장 벤치마크 (베타 계산 기준)
MARKET_TICKER = "SPY"

# yfinance 결과 캐시 (5분 TTL)
_PRICE_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 300


def _fetch_returns(tickers: list[str], years: int = 3) -> "dict[str, np.ndarray]":
    """yfinance로 일별 수익률 DataFrame 반환. 캐시 적용."""
    import yfinance as yf

    cache_key = f"{','.join(sorted(tickers))}:{years}"
    if cache_key in _PRICE_CACHE:
        ts, data = _PRICE_CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return data  # type: ignore[return-value]

    import pandas as pd
    end = pd.Timestamp.today()
    start = end - pd.DateOffset(years=years)

    raw = yf.download(tickers, start=start.strftime("%Y-%m-%d"),
                      end=end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)

    prices = raw["Close"] if hasattr(raw["Close"], "columns") else raw["Close"].to_frame()
    returns: dict[str, np.ndarray] = {}
    for t in tickers:
        if t in prices.columns:
            s = prices[t].dropna()
            if len(s) > 20:
                returns[t] = s.pct_change().dropna().values
    _PRICE_CACHE[cache_key] = (time.time(), returns)
    return returns


def _align_returns(returns_map: dict[str, np.ndarray]) -> tuple[list[str], np.ndarray]:
    """공통 길이로 맞춤. 가장 짧은 시리즈에 맞춤."""
    if not returns_map:
        return [], np.array([])
    min_len = min(len(v) for v in returns_map.values())
    tickers = list(returns_map.keys())
    mat = np.column_stack([returns_map[t][-min_len:] for t in tickers])
    return tickers, mat


# ---------------------------------------------------------------------------
# 리스크 패리티 최적화
# ---------------------------------------------------------------------------

def _risk_parity_weights(cov: np.ndarray, bounds: list[tuple[float, float]]) -> np.ndarray:
    """
    각 자산의 위험 기여도가 동등해지도록 비중 결정.
    목적함수: Σ(RC_i/총위험 - 1/n)² 최소화
    """
    from scipy.optimize import minimize

    n = len(cov)

    def risk_contributions(w: np.ndarray) -> np.ndarray:
        port_vol = float(np.sqrt(w @ cov @ w))
        if port_vol < 1e-10:
            return np.ones(n) / n
        return (w * (cov @ w)) / port_vol

    def objective(w: np.ndarray) -> float:
        rc = risk_contributions(w)
        target = rc.sum() / n
        return float(np.sum((rc - target) ** 2))

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    w0 = np.ones(n) / n
    result = minimize(objective, w0, method="SLSQP",
                      bounds=bounds, constraints=constraints,
                      options={"maxiter": 1000, "ftol": 1e-9})
    if not result.success:
        # 수렴 실패 시 균등 비중 반환
        return w0
    w = np.maximum(result.x, 0)
    return w / w.sum()


# ---------------------------------------------------------------------------
# 지표 계산
# ---------------------------------------------------------------------------

def _annualize(daily_vol: float) -> float:
    return daily_vol * np.sqrt(252)


def _downside_vol(portfolio_returns: np.ndarray) -> float:
    """하방변동성 (손실 구간만) 연환산."""
    neg = portfolio_returns[portfolio_returns < 0]
    if len(neg) < 5:
        return 0.0
    return _annualize(float(np.std(neg, ddof=1)))


def _downside_risk_score(downside_vol_annual: float) -> float:
    """하방변동성 → 0~100 스케일. 30% 이상이면 100."""
    return min(downside_vol_annual / 0.30, 1.0) * 100


def _sortino(expected_return: float, downside_vol: float, risk_free: float = 0.035) -> float:
    """소르티노 비율. 분모 0이면 0 반환."""
    return (expected_return - risk_free) / downside_vol if downside_vol > 1e-6 else 0.0


def _beta(portfolio_returns: np.ndarray, market_returns: np.ndarray) -> float:
    """포트폴리오 베타 (market 기준)."""
    n = min(len(portfolio_returns), len(market_returns))
    p, m = portfolio_returns[-n:], market_returns[-n:]
    var_m = float(np.var(m, ddof=1))
    return float(np.cov(p, m, ddof=1)[0, 1] / var_m) if var_m > 1e-10 else 1.0


def _max_drawdown(returns: np.ndarray) -> float:
    """최대 낙폭(MDD). peak-to-trough 최대 하락폭. 음수 반환 (-0.15 = -15%)."""
    if len(returns) < 2:
        return 0.0
    cumulative = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cumulative)
    dd = (cumulative - peak) / peak
    return float(dd.min())


# ---------------------------------------------------------------------------
# 비중 상한: risk_level 반영
# ---------------------------------------------------------------------------

def _bounds_for_risk_level(asset_ids: list[str], risk_level: Optional[str]) -> list[tuple[float, float]]:
    """
    risk_level에 따라 자산별 비중 상한 조정.
    '낮음': 주식 ETF 상한 낮추고 안전자산(금·달러) 상한 올림.
    '높음': 주식 ETF 상한 높임.
    """
    equity_cats = {"국내주식", "해외주식"}
    safe_cats = {"달러", "원자재"}

    lo = 0.02   # 최소 비중 2%

    if risk_level == "낮음":
        equity_hi, safe_hi, other_hi = 0.20, 0.40, 0.30
    elif risk_level == "높음":
        equity_hi, safe_hi, other_hi = 0.45, 0.25, 0.35
    else:  # 중립 또는 None
        equity_hi, safe_hi, other_hi = 0.35, 0.35, 0.30

    result = []
    for aid in asset_ids:
        cat = ASSETS[aid]["category"]
        if cat in equity_cats:
            result.append((lo, equity_hi))
        elif cat in safe_cats:
            result.append((lo, safe_hi))
        else:
            result.append((lo, other_hi))
    return result


# ---------------------------------------------------------------------------
# 메인 진입점
# ---------------------------------------------------------------------------

@dataclass
class OptimizationResult:
    weights: dict[str, float]           # {asset_id: weight}
    expected_return: float              # 연환산 기대수익률
    downside_volatility: float          # 연환산 하방변동성
    downside_risk_score: float          # 0~100 위험 스케일
    sortino_ratio: float
    beta: float
    max_drawdown: float = 0.0           # 음수 (예: -0.18 = -18%)
    provisional: bool = False
    warnings: list[str] = field(default_factory=list)
    asset_names: dict[str, str] = field(default_factory=dict)


def optimize(
    risk_level: Optional[str] = None,
    excluded_sectors: Optional[list[str]] = None,
    target_return_min: Optional[float] = None,
    target_return_max: Optional[float] = None,
    provisional: bool = False,
    years: int = 3,
) -> OptimizationResult:
    """
    리스크 패리티 포트폴리오 최적화.

    risk_level: "높음"|"중립"|"낮음" — 비중 상한 조정
    excluded_sectors: ["tobacco", ...] — 해당 자산 제외
    """
    warnings: list[str] = []

    # 1. 제외 자산 필터링
    excluded_cats: set[str] = set()
    for sec in (excluded_sectors or []):
        excluded_cats.update(SECTOR_EXCLUSION.get(sec, []))

    active_ids = [aid for aid, meta in ASSETS.items()
                  if meta["category"] not in excluded_cats]
    active_tickers = [ASSETS[aid]["ticker"] for aid in active_ids]

    # 시장 벤치마크 별도 수집
    all_tickers = list(set(active_tickers + [MARKET_TICKER]))

    # 2. 가격 데이터 수집
    returns_map = _fetch_returns(all_tickers, years=years)

    if len(returns_map) < 2:
        raise RuntimeError("데이터를 충분히 수집할 수 없습니다. 네트워크를 확인하세요.")

    # 3. 유효 자산만 추림
    valid_ids = [aid for aid in active_ids if ASSETS[aid]["ticker"] in returns_map]
    if len(valid_ids) < 2:
        raise RuntimeError("유효 자산이 2개 미만입니다.")

    valid_tickers = [ASSETS[aid]["ticker"] for aid in valid_ids]
    _, ret_matrix = _align_returns({t: returns_map[t] for t in valid_tickers})

    # 4. 공분산 행렬 + 리스크 패리티
    cov = np.cov(ret_matrix.T, ddof=1)
    bounds = _bounds_for_risk_level(valid_ids, risk_level)
    weights = _risk_parity_weights(cov, bounds)

    # 5. 포트폴리오 수익률 시계열
    port_returns = ret_matrix @ weights

    # 6. 지표 계산
    exp_ret = float(np.mean(port_returns)) * 252
    dv = _downside_vol(port_returns)
    dv_score = _downside_risk_score(dv)
    sortino = _sortino(exp_ret, dv)

    market_returns = returns_map.get(MARKET_TICKER, np.zeros(len(port_returns)))
    beta = _beta(port_returns, market_returns)
    mdd = _max_drawdown(port_returns)

    # 7. 목표수익률 대비 경고
    if target_return_min is not None and exp_ret < target_return_min:
        warnings.append(
            f"포트폴리오 기대수익률({exp_ret*100:.1f}%)이 목표 하한({target_return_min*100:.1f}%)에 미치지 못합니다. "
            "리스크 성향 또는 목표를 재검토하세요."
        )
    if provisional:
        warnings.append("핵심 요인 신뢰도가 낮아 포트폴리오 제약을 잠정 적용했습니다.")

    return OptimizationResult(
        weights={valid_ids[i]: float(weights[i]) for i in range(len(valid_ids))},
        expected_return=exp_ret,
        downside_volatility=dv,
        downside_risk_score=dv_score,
        sortino_ratio=sortino,
        beta=beta,
        max_drawdown=mdd,
        provisional=provisional,
        warnings=warnings,
        asset_names={aid: ASSETS[aid]["name"] for aid in valid_ids},
    )


# ---------------------------------------------------------------------------
# 3안 동시 산출 (안정형 / 균형형 / 성장형)
# ---------------------------------------------------------------------------

PLAN_DEFS = [
    ("conservative", "낮음", "안정형", "원금 보존 우선. 채권·달러·금 등 안전자산 비중을 확대."),
    ("balanced",     "중립", "균형형", "리스크 패리티 표준. 자산별 위험 기여도를 균등하게 배분."),
    ("growth",       "높음", "성장형", "기대수익 우선. 국내·해외 주식 비중을 확대."),
]


def optimize_plans(
    base_risk_level: Optional[str] = None,
    excluded_sectors: Optional[list[str]] = None,
    target_return_min: Optional[float] = None,
    target_return_max: Optional[float] = None,
    provisional: bool = False,
    years: int = 3,
) -> dict:
    """안정·균형·성장 세 가지 안을 동시에 산출.
    base_risk_level: 고객의 위험 성향. 일치하는 안에 'recommended' 표시."""
    plans: dict[str, dict] = {}
    for key, risk, name, desc in PLAN_DEFS:
        r = optimize(
            risk_level=risk,
            excluded_sectors=excluded_sectors,
            target_return_min=target_return_min,
            target_return_max=target_return_max,
            provisional=provisional,
            years=years,
        )
        plans[key] = {"result": r, "name": name, "description": desc}

    recommended = {"낮음": "conservative", "중립": "balanced", "높음": "growth"}.get(
        base_risk_level or "", "balanced"
    )
    return {"plans": plans, "recommended": recommended}
