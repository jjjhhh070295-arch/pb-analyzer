"use client";
import { useState, useEffect } from "react";
import { api, type PortfolioResult, type PortfolioWeight, type ConfirmedPortfolio, type TaxStrategyResult, type TaxProductCandidate, type TaxStrategyRanked } from "@/lib/api";

const CATEGORY_COLOR: Record<string, string> = {
  "국내주식": "bg-blue-900",
  "해외주식": "bg-blue-700",
  "리츠":    "bg-indigo-500",
  "원자재":  "bg-amber-500",
  "달러":    "bg-amber-300",
};

// PB 전용 — 주간 추천 ETF (고객 화면 미노출). 운용본부 권고를 임의 반영해 운영.
const WEEKLY_RECOMMENDED = [
  {
    name: "KODEX 200 TR",
    code: "278530",
    category: "국내주식",
    reason: "국내 대형주 코어 노출, 배당 재투자로 장기 복리 효과",
  },
  {
    name: "KODEX 미국S&P500",
    code: "379800",
    category: "해외주식",
    reason: "글로벌 대형주 분산, 환노출형으로 달러 자산 효과 동반",
  },
  {
    name: "KODEX 골드선물(H)",
    code: "132030",
    category: "원자재",
    reason: "환헤지형 금, 인플레이션·지정학 리스크 헤지 수단",
  },
];

interface Props {
  sessionId: string;
  confirmed: boolean;
  initialConfirmedPortfolio?: ConfirmedPortfolio | null;
  initialConfirmedTaxStrategy?: TaxStrategyResult | null;
  onPortfolioChange?: () => void;
}

type EditWeight = PortfolioWeight & { weight_pct: number };

export default function PortfolioTab({ sessionId, confirmed, initialConfirmedPortfolio, initialConfirmedTaxStrategy, onPortfolioChange }: Props) {
  const [result, setResult] = useState<PortfolioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 편집 상태 — 확정본 있으면 그걸로 초기화
  const [editWeights, setEditWeights] = useState<EditWeight[] | null>(
    initialConfirmedPortfolio
      ? initialConfirmedPortfolio.weights.map(w => ({ ...w }))
      : null
  );
  const [editing, setEditing] = useState(false);
  const [savingPortfolio, setSavingPortfolio] = useState(false);
  const [note, setNote] = useState(initialConfirmedPortfolio?.note ?? "");
  const [isConfirmedView, setIsConfirmedView] = useState(!!initialConfirmedPortfolio);

  // 절세 전략 — 확정본이 이미 있으면 그걸로 시작, 없으면 분석 자동 호출
  const [taxStrategy, setTaxStrategy] = useState<TaxStrategyResult | null>(
    initialConfirmedTaxStrategy ?? null
  );
  const [taxLoading, setTaxLoading] = useState(false);
  const [taxConfirmed, setTaxConfirmed] = useState(!!initialConfirmedTaxStrategy);
  const [taxNote, setTaxNote] = useState(initialConfirmedTaxStrategy && "note" in initialConfirmedTaxStrategy
    ? ((initialConfirmedTaxStrategy as { note?: string | null }).note ?? "") : "");
  const [taxSaving, setTaxSaving] = useState(false);

  useEffect(() => {
    if (!confirmed) return;
    if (taxStrategy) return; // 이미 확정본 또는 분석 결과 있음
    setTaxLoading(true);
    api.portfolio.taxStrategy(sessionId)
      .then(setTaxStrategy)
      .catch(() => {/* 절세 전략 실패는 조용히 무시 — 메인 흐름 방해 X */})
      .finally(() => setTaxLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, confirmed]);

  const reanalyzeTax = () => {
    setTaxLoading(true);
    api.portfolio.taxStrategy(sessionId)
      .then(s => { setTaxStrategy(s); setTaxConfirmed(false); })
      .catch(() => {})
      .finally(() => setTaxLoading(false));
  };

  const confirmTax = async () => {
    if (!taxStrategy) return;
    setTaxSaving(true);
    setError("");
    try {
      await api.portfolio.confirmTaxStrategy(sessionId, { ...taxStrategy, note: taxNote || undefined });
      setTaxConfirmed(true);
      onPortfolioChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "절세 전략 송출 실패");
    } finally {
      setTaxSaving(false);
    }
  };

  const unconfirmTax = async () => {
    if (!window.confirm("확정된 절세 전략을 해제합니다. 고객 화면에서도 사라집니다.")) return;
    setTaxSaving(true);
    try {
      await api.portfolio.clearConfirmedTaxStrategy(sessionId);
      setTaxConfirmed(false);
      onPortfolioChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "해제 실패");
    } finally {
      setTaxSaving(false);
    }
  };

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await api.portfolio.optimize(sessionId);
      setResult(r);
      // 편집 가능한 가중치 초기화 (최적화 결과로)
      setEditWeights(r.weights.map(w => ({ ...w })));
    } catch (e) {
      setError(e instanceof Error ? e.message : "최적화 실패");
    } finally {
      setLoading(false);
    }
  };

  const total = editWeights ? editWeights.reduce((s, w) => s + (w.weight_pct || 0), 0) : 0;
  const ok = Math.abs(total - 100) < 0.5;

  const setW = (i: number, pct: number) => {
    if (!editWeights) return;
    const next = [...editWeights];
    next[i] = { ...next[i], weight_pct: Math.max(0, Math.min(100, pct)) };
    setEditWeights(next);
  };

  const normalize = () => {
    if (!editWeights || total === 0) return;
    const scale = 100 / total;
    setEditWeights(editWeights.map(w => ({ ...w, weight_pct: Math.round(w.weight_pct * scale * 10) / 10 })));
  };

  const confirmPortfolio = async () => {
    if (!editWeights || !ok) return;
    setSavingPortfolio(true);
    setError("");
    try {
      await api.portfolio.confirm(sessionId, {
        weights: editWeights.filter(w => w.weight_pct > 0),
        note: note || undefined,
        metrics: result?.metrics ?? undefined,
      });
      setIsConfirmedView(true);
      setEditing(false);
      onPortfolioChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "포트폴리오 확정 실패");
    } finally {
      setSavingPortfolio(false);
    }
  };

  const unconfirm = async () => {
    if (!window.confirm("확정된 포트폴리오를 해제합니다. 고객 화면에서도 사라집니다.")) return;
    setSavingPortfolio(true);
    try {
      await api.portfolio.clearConfirmed(sessionId);
      setIsConfirmedView(false);
      onPortfolioChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "해제 실패");
    } finally {
      setSavingPortfolio(false);
    }
  };

  if (!confirmed) {
    return (
      <div className="card-premium px-6 py-8 text-center text-sm text-slate-500">
        PB 검수 확정 후 포트폴리오 최적화를 실행할 수 있습니다.
      </div>
    );
  }

  // 1) 아직 한 번도 최적화 안 했고 확정 포트폴리오도 없는 상태
  if (!editWeights && !loading) {
    return (
      <div className="card-premium px-6 py-12 text-center">
        <p className="text-3xl mb-3">📊</p>
        <p className="text-sm text-slate-600 mb-1 font-medium">리스크 패리티 포트폴리오 최적화</p>
        <p className="text-xs text-slate-400 mb-5">7요인 제약을 바탕으로 자산 배분을 산출합니다</p>
        <button onClick={run} className="btn-navy px-7 py-2.5 rounded-lg text-sm shadow-sm">
          최적화 실행
        </button>
        <p className="text-[11px] text-slate-400 mt-3">실시간 가격 데이터 수집 포함 · 약 10~30초</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card-premium px-6 py-14 text-center text-slate-500">
        <p className="text-2xl mb-2 animate-spin inline-block">⏳</p>
        <p className="text-sm">시장 데이터 수집 및 최적화 중…</p>
      </div>
    );
  }

  if (error && !editWeights) {
    return (
      <div className="card-premium px-6 py-8 text-center">
        <p className="text-red-500 text-sm mb-3">{error}</p>
        <button onClick={run} className="text-navy text-sm font-medium hover:underline">재시도</button>
      </div>
    );
  }

  if (!editWeights) return null;

  const m = result?.metrics ?? initialConfirmedPortfolio?.metrics ?? null;
  const riskTone = m && m.downside_risk_score < 33 ? "text-emerald-700" : m && m.downside_risk_score < 66 ? "text-amber-700" : "text-red-700";

  return (
    <div className="space-y-5">
      {result?.provisional && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          ⚠ 핵심 요인 신뢰도가 낮아 잠정 결과입니다. 추가 정보 확인 후 재실행을 권장합니다.
        </div>
      )}
      {result?.warnings.map((w, i) => (
        <div key={i} className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-2.5 text-sm text-orange-800">{w}</div>
      ))}
      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span><button onClick={() => setError("")} className="text-xs underline">닫기</button>
        </div>
      )}

      {/* 확정 상태 배너 */}
      {isConfirmedView && !editing && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-amber-900">✓ 확정 포트폴리오</p>
            <p className="text-[11px] text-amber-700 mt-0.5">고객 화면에 송출됩니다.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setEditing(true)}
              className="text-xs text-navy font-medium hover:underline">수정</button>
            <button onClick={unconfirm} disabled={savingPortfolio}
              className="text-xs text-red-600 font-medium hover:underline disabled:opacity-50">확정 해제</button>
          </div>
        </div>
      )}

      {/* 지표 카드 (최적화 결과가 있을 때만) */}
      {m && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard label="기대수익률" value={`${(m.expected_return_pct ?? 0).toFixed(1)}%`} sub="연환산" valueColor="text-navy" />
          <MetricCard label="위험 점수" value={`${(m.downside_risk_score ?? 0).toFixed(0)}/100`} sub="하방변동성" valueColor={riskTone} />
          <MetricCard label="소르티노" value={(m.sortino_ratio ?? 0).toFixed(2)} sub="위험조정 성과" valueColor="text-gold" />
          <MetricCard label="베타" value={(m.beta ?? 0).toFixed(2)} sub="vs S&P 500" valueColor="text-slate-700" />
        </div>
      )}

      {/* 자산 배분 */}
      <div className="card-premium p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <span className="w-1 h-4 bg-gold rounded-sm" />
            자산 배분 {editing && <span className="text-xs text-gold font-normal">(수정 중)</span>}
          </p>
          {!editing && !isConfirmedView && (
            <button onClick={() => setEditing(true)} className="text-xs text-navy font-medium hover:underline">
              ✎ 비중 수정
            </button>
          )}
        </div>

        {/* 막대 미리보기 */}
        <div className="flex h-7 rounded-lg overflow-hidden mb-4 ring-1 ring-slate-200">
          {editWeights.filter(w => w.weight_pct > 0).map(w => (
            <div key={w.asset_id}
              className={`${CATEGORY_COLOR[w.category] ?? "bg-slate-400"} transition-all`}
              style={{ width: `${(w.weight_pct / Math.max(total, 1)) * 100}%` }}
              title={`${w.name}: ${w.weight_pct.toFixed(1)}%`} />
          ))}
        </div>

        {/* 항목 리스트 — 편집 모드면 input */}
        <ul className="space-y-2">
          {editWeights.map((w, i) => (
            <li key={w.asset_id} className="flex items-center gap-3 text-sm">
              <span className={`w-2.5 h-2.5 rounded-sm flex-shrink-0 ${CATEGORY_COLOR[w.category] ?? "bg-slate-400"}`} />
              <span className="flex-1 text-slate-700">{w.name}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider w-16">{w.category}</span>
              {editing ? (
                <input
                  type="number" step="0.1" min="0" max="100"
                  value={w.weight_pct}
                  onChange={e => setW(i, parseFloat(e.target.value || "0"))}
                  className="w-20 border border-slate-300 rounded px-2 py-1 text-right text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 tabular-nums"
                />
              ) : (
                <span className="font-semibold text-slate-900 w-14 text-right tabular-nums">{w.weight_pct.toFixed(1)}%</span>
              )}
            </li>
          ))}
        </ul>

        {/* 합계 + 정규화 (편집 모드) */}
        {editing && (
          <div className="mt-4 pt-4 border-t border-slate-200 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">합계</span>
              <div className="flex items-center gap-3">
                <button onClick={normalize}
                  className="text-xs text-slate-500 hover:text-navy underline">100%로 정규화</button>
                <span className={`font-bold tabular-nums ${ok ? "text-emerald-600" : "text-red-600"}`}>
                  {total.toFixed(1)}%
                </span>
              </div>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-500 mb-1 uppercase tracking-wider">PB 메모 (고객 화면 노출)</label>
              <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                placeholder="예: 안정성 위주로 미국 채권 비중을 늘렸습니다."
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white resize-none focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900" />
            </div>
          </div>
        )}
      </div>

      {/* PB 전용 — 주간 추천 ETF */}
      <div className="card-premium p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <span className="w-1 h-4 bg-gold rounded-sm" />
            📌 주간 추천 ETF
          </p>
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">
            PB 전용 · 고객 미노출
          </span>
        </div>
        <p className="text-xs text-slate-500 mb-4">이번 주 운용본부 권고. 고객 상황에 맞춰 검토 후 위 비중에 반영하세요.</p>
        <ul className="space-y-2">
          {WEEKLY_RECOMMENDED.map(item => (
            <li key={item.code}
              className="border border-slate-200 rounded-lg px-4 py-3 hover:border-gold transition-colors">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-sm font-semibold text-slate-900">{item.name}</span>
                <span className="text-[10px] font-mono text-slate-400 tracking-wider">{item.code}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider font-medium ${CATEGORY_COLOR[item.category] ?? "bg-slate-400"} text-white`}>
                  {item.category}
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{item.reason}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* 절세 전략 */}
      <TaxStrategyCard
        loading={taxLoading}
        strategy={taxStrategy}
        onRefresh={reanalyzeTax}
        confirmed={taxConfirmed}
        saving={taxSaving}
        note={taxNote}
        onNoteChange={setTaxNote}
        onConfirm={confirmTax}
        onUnconfirm={unconfirmTax}
      />

      {/* 액션 버튼 */}
      <div className="flex justify-between items-center">
        <button onClick={run} className="text-xs text-slate-400 hover:text-navy underline transition-colors">
          최적화 재실행
        </button>

        {editing ? (
          <div className="flex gap-2">
            <button onClick={() => setEditing(false)} disabled={savingPortfolio}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">취소</button>
            <button onClick={confirmPortfolio} disabled={!ok || savingPortfolio}
              className="btn-gold px-5 py-2 rounded-lg text-sm shadow-md disabled:opacity-40">
              {savingPortfolio ? "확정 중…" : "✓ 포트폴리오 확정"}
            </button>
          </div>
        ) : !isConfirmedView ? (
          <button onClick={confirmPortfolio} disabled={savingPortfolio}
            className="btn-gold px-5 py-2 rounded-lg text-sm shadow-md">
            {savingPortfolio ? "확정 중…" : "✓ 이 결과로 확정"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, valueColor }: { label: string; value: string; sub: string; valueColor: string }) {
  return (
    <div className="card-premium p-4 text-center">
      <p className="text-[11px] text-slate-400 mb-1 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold ${valueColor} tabular-nums`}>{value}</p>
      <p className="text-[11px] text-slate-400 mt-1">{sub}</p>
    </div>
  );
}

const PRIORITY_STYLE = {
  high:   { badge: "bg-gold text-white",         label: "1순위 검토" },
  medium: { badge: "bg-blue-100 text-navy",      label: "2순위 검토" },
  low:    { badge: "bg-slate-100 text-slate-600", label: "참고" },
} as const;

const KRW = new Intl.NumberFormat("ko-KR");

function TaxStrategyCard({ loading, strategy, onRefresh, confirmed, saving, note, onNoteChange, onConfirm, onUnconfirm }: {
  loading: boolean;
  strategy: TaxStrategyResult | null;
  onRefresh: () => void;
  confirmed: boolean;
  saving: boolean;
  note: string;
  onNoteChange: (v: string) => void;
  onConfirm: () => void;
  onUnconfirm: () => void;
}) {
  if (loading && !strategy) {
    return (
      <div className="card-premium px-6 py-8 text-center text-slate-500 text-sm">
        <span className="animate-spin inline-block mr-2">⏳</span> 절세 전략 분석 중…
      </div>
    );
  }
  if (!strategy) return null;

  // ranked priority 순서로 정렬한 후보 리스트
  const cands = [...strategy.candidates];
  const priorityMap = new Map(strategy.ranked.map(r => [r.product_id, r]));
  cands.sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 } as const;
    const ar = priorityMap.get(a.product_id)?.priority ?? "low";
    const br = priorityMap.get(b.product_id)?.priority ?? "low";
    return order[ar] - order[br];
  });

  return (
    <div className="card-premium p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <span className="w-1 h-4 bg-gold rounded-sm" />
          💼 절세 전략 분석
        </p>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">
            PB 검토용 · 자문 아님
          </span>
          <button onClick={onRefresh}
            className="text-xs text-slate-400 hover:text-navy underline">재분석</button>
        </div>
      </div>

      {/* 전략 요약 */}
      {strategy.summary && (
        <div className="bg-gold-light/40 border-l-4 border-gold rounded px-4 py-3 mb-4 text-sm text-slate-700 leading-relaxed">
          {strategy.summary}
        </div>
      )}

      {/* 상품 카드 리스트 */}
      <ul className="space-y-3">
        {cands.map(c => {
          const rk = priorityMap.get(c.product_id);
          const ps = rk ? PRIORITY_STYLE[rk.priority] : PRIORITY_STYLE.low;
          return (
            <li key={c.product_id}
              className={`border rounded-lg p-4 transition-colors ${c.eligible ? "border-slate-200 hover:border-gold" : "border-slate-200 bg-slate-50/50"}`}>
              <div className="flex items-start justify-between gap-3 mb-1.5 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${ps.badge}`}>{ps.label}</span>
                  <span className="text-sm font-semibold text-slate-900">{c.name}</span>
                  {!c.eligible && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-500">자격 확인</span>
                  )}
                </div>
                {c.estimated_saving_won != null && (
                  <div className="text-right">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider block">예상 절감</span>
                    <span className="text-sm font-bold text-gold tabular-nums">
                      {KRW.format(c.estimated_saving_won)}원/년
                    </span>
                  </div>
                )}
              </div>
              <p className="text-xs text-slate-500 mb-2">{c.one_liner}</p>
              <p className="text-[11px] text-slate-600 mb-2">📐 {c.limit_text}</p>

              {rk && (
                <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                  <p className="text-xs text-slate-700">
                    <span className="text-gold font-semibold">검토 이유 · </span>{rk.reason}
                  </p>
                  {rk.caveats && (
                    <p className="text-xs text-slate-500">
                      <span className="font-semibold">⚠ 주의 · </span>{rk.caveats}
                    </p>
                  )}
                </div>
              )}

              <p className="text-[10px] text-slate-400 mt-2">{c.eligibility_note}</p>
            </li>
          );
        })}
      </ul>

      <p className="text-[10px] text-slate-400 mt-4 leading-relaxed">
        본 분석은 PB 검토를 돕기 위한 자료이며 세무 자문이 아닙니다.
        실제 가입·매도 의사결정 전 한도·자격·소득구간을 반드시 확인하세요.
      </p>

      {/* 고객 송출 — 확정 배너 또는 확정 버튼 */}
      {confirmed ? (
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-300 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-amber-900">✓ 절세 전략 확정 — 고객 화면 송출 중</p>
              {note && <p className="text-xs text-amber-800 mt-1">📝 {note}</p>}
            </div>
            <button onClick={onUnconfirm} disabled={saving}
              className="text-xs text-red-600 hover:underline font-medium disabled:opacity-50">
              {saving ? "처리중…" : "송출 해제"}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 pt-4 border-t border-slate-100 space-y-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 mb-1 uppercase tracking-wider">PB 코멘트 (고객 화면 노출)</label>
            <textarea value={note} onChange={e => onNoteChange(e.target.value)} rows={2}
              placeholder="예: ISA·연금저축 동시 활용을 우선 권고드립니다."
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white resize-none focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900" />
          </div>
          <button onClick={onConfirm} disabled={saving}
            className="btn-gold w-full py-2.5 rounded-lg text-sm shadow-md disabled:opacity-50">
            {saving ? "송출 중…" : "✓ 이 절세 전략 고객 화면에 송출"}
          </button>
        </div>
      )}
    </div>
  );
}
