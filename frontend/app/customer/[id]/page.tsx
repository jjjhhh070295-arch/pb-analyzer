"use client";
import { useEffect, useState, use } from "react";
import { api, type Session } from "@/lib/api";

const fmtPct = (n: number | null) => n == null ? null : `${(n * 100).toFixed(0)}%`;
const fmtAmt = (n: number | null) =>
  n == null ? null : n >= 100000000 ? `${(n / 100000000).toFixed(1)}억` : `${(n / 10000).toLocaleString()}만`;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 border-b border-slate-100 last:border-b-0">
      <dt className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-1 sm:mt-0 sm:col-span-2 text-sm text-slate-900 leading-relaxed">{children}</dd>
    </div>
  );
}

export default function CustomerSessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "not_confirmed" | "error">("loading");

  useEffect(() => {
    api.sessions.get(id)
      .then(s => {
        if (!("result" in s)) { setStatus("error"); return; }
        const sess = s as Session;
        if (sess.status !== "확정") { setStatus("not_confirmed"); return; }
        setSession(sess);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [id]);

  if (status === "loading") return <Blank text="불러오는 중…" />;
  if (status === "not_confirmed") return <Blank text="아직 확정되지 않은 자료입니다." />;
  if (status === "error" || !session) return <Blank text="자료를 찾을 수 없습니다." />;

  const r = session.result;
  const returnMin = fmtPct(r.goal_return.return_min);
  const returnMax = fmtPct(r.goal_return.return_max);
  const returnStr = r.goal_return.raw_text
    ? r.goal_return.raw_text
    : returnMin && returnMax && returnMin !== returnMax
      ? `연 ${returnMin} ~ ${returnMax}`
      : returnMin ? `연 ${returnMin}` : "미확인";

  const riskLevel = (() => {
    const b = r.risk_tolerance.binding;
    if (b === "willingness") return r.risk_tolerance.willingness.level;
    if (b === "capacity") return r.risk_tolerance.capacity.level;
    return r.risk_tolerance.willingness.level ?? r.risk_tolerance.capacity.level;
  })();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-header-gradient text-white">
        <div className="max-w-3xl mx-auto px-6 py-8 text-center">
          <p className="text-gold text-[11px] font-semibold tracking-[0.2em] mb-2">PRIVATE WEALTH ADVISORY</p>
          <h1 className="text-2xl font-bold tracking-tight">{session.customer_name} <span className="text-blue-100 font-normal text-lg">고객님</span></h1>
          <p className="text-blue-100 text-xs mt-2">{session.consult_date} · 담당 {session.pb_name}</p>
        </div>
        <div className="gold-accent-line" />
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="card-premium overflow-hidden">
          <div className="px-7 py-4 bg-slate-50 border-b border-slate-200">
            <h2 className="text-sm font-bold text-navy tracking-tight">투자 성향 분석 요약</h2>
            <p className="text-[11px] text-slate-500 mt-0.5">고객님과의 상담 내용을 바탕으로 정리한 자산관리 방향입니다.</p>
          </div>
          <dl className="px-7">
            <Row label="목표 수익률">{returnStr}</Row>
            <Row label="위험 성향">{riskLevel ?? "미확인"}</Row>
            <Row label="투자 기간">{r.horizon.years != null ? `${r.horizon.years}년` : "미확인"}</Row>

            {(r.tax.items.length > 0 || r.tax.annual_financial_income != null) && (
              <Row label="세금 고려 사항">
                <ul className="space-y-1">
                  {r.tax.annual_financial_income != null && (
                    <li>연간 금융소득 <span className="font-semibold">{fmtAmt(r.tax.annual_financial_income)}</span></li>
                  )}
                  {r.tax.items.map((item, i) => <li key={i}>· {item}</li>)}
                </ul>
              </Row>
            )}

            {r.liquidity.events.length > 0 && (
              <Row label="유동성 계획">
                <ul className="space-y-1">
                  {r.liquidity.events.map((e, i) => (
                    <li key={i}>
                      {e.when && <span className="text-slate-600">{e.when}</span>}
                      {e.amount != null && <span className="ml-2 font-semibold text-navy">{fmtAmt(e.amount)}</span>}
                      {e.purpose && <span className="text-slate-500 ml-1.5 text-xs">({e.purpose})</span>}
                    </li>
                  ))}
                </ul>
              </Row>
            )}

            {r.legal.items.length > 0 && (
              <Row label="법적 제약">
                <ul className="space-y-1">{r.legal.items.map((item, i) => <li key={i}>· {item}</li>)}</ul>
              </Row>
            )}

            {(r.unique.notes.length > 0 || r.unique.excluded_sectors.length > 0) && (
              <Row label="기타 고려 사항">
                <ul className="space-y-1">
                  {r.unique.notes.map((n, i) => <li key={i}>· {n}</li>)}
                  {r.unique.excluded_sectors.length > 0 && (
                    <li className="text-gold font-semibold text-xs tracking-wide mt-1">배제 업종: {r.unique.excluded_sectors.join(", ")}</li>
                  )}
                </ul>
              </Row>
            )}
          </dl>
        </div>

        {r.confirmed_portfolio && r.confirmed_portfolio.weights.length > 0 && (
          <PortfolioSection portfolio={r.confirmed_portfolio} />
        )}

        {r.confirmed_tax_strategy && r.confirmed_tax_strategy.candidates && (
          <TaxStrategySection strategy={r.confirmed_tax_strategy} />
        )}

        <p className="mt-8 text-[11px] text-center text-slate-400 leading-relaxed">
          본 자료는 참고용 분석 결과이며, 최종 투자 결정과 책임은 고객에게 있습니다.<br/>
          자세한 사항은 담당 PB에게 문의해주시기 바랍니다.
        </p>
      </main>
    </div>
  );
}

const CATEGORY_COLOR_PUBLIC: Record<string, string> = {
  "국내주식": "bg-blue-900",
  "해외주식": "bg-blue-700",
  "리츠":    "bg-indigo-500",
  "원자재":  "bg-amber-500",
  "달러":    "bg-amber-300",
};

function PortfolioSection({ portfolio }: { portfolio: NonNullable<Session["result"]["confirmed_portfolio"]> }) {
  const m = portfolio.metrics as (Record<string, number> | null | undefined);
  const expPct = m && typeof m["expected_return_pct"] === "number" ? m["expected_return_pct"] : null;
  const afterPct = m && typeof m["after_tax_return_pct"] === "number" ? m["after_tax_return_pct"] : null;
  const riskScore = m && typeof m["downside_risk_score"] === "number" ? m["downside_risk_score"] : null;
  const taxRate = m && typeof m["tax_rate_applied"] === "number" ? m["tax_rate_applied"] : null;

  const riskTone = riskScore == null ? "text-slate-500"
    : riskScore < 33 ? "text-emerald-700"
    : riskScore < 66 ? "text-amber-700"
    : "text-red-700";

  const riskLabel = riskScore == null ? "—"
    : riskScore < 33 ? "안정"
    : riskScore < 66 ? "보통"
    : "공격";

  return (
    <div className="card-premium overflow-hidden mt-6">
      <div className="px-7 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-navy tracking-tight">추천 포트폴리오</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">담당 PB가 직접 검토하여 확정한 자산 배분입니다.</p>
        </div>
        <span className="badge-confirmed text-[10px] px-2.5 py-0.5 rounded">확정</span>
      </div>

      <div className="px-7 py-6">
        {/* 핵심 지표 3개 */}
        {(expPct != null || afterPct != null || riskScore != null) && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="text-center bg-slate-50 rounded-lg py-4">
              <p className="text-[11px] text-slate-500 mb-1 uppercase tracking-wider">기대수익률</p>
              <p className="text-2xl font-bold text-navy tabular-nums">
                {expPct != null ? `${expPct.toFixed(1)}%` : "—"}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">연환산</p>
            </div>
            <div className="text-center bg-gold-light/30 rounded-lg py-4 ring-1 ring-gold/30">
              <p className="text-[11px] text-slate-500 mb-1 uppercase tracking-wider">세후 수익률</p>
              <p className="text-2xl font-bold text-gold tabular-nums">
                {afterPct != null ? `${afterPct.toFixed(1)}%` : "—"}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {taxRate != null ? `세율 ${(taxRate * 100).toFixed(1)}% 적용` : "세금 차감"}
              </p>
            </div>
            <div className="text-center bg-slate-50 rounded-lg py-4">
              <p className="text-[11px] text-slate-500 mb-1 uppercase tracking-wider">위험지수</p>
              <p className={`text-2xl font-bold tabular-nums ${riskTone}`}>
                {riskScore != null ? `${riskScore.toFixed(0)}` : "—"}<span className="text-base text-slate-400">/100</span>
              </p>
              <p className={`text-[11px] mt-0.5 ${riskTone}`}>{riskLabel}</p>
            </div>
          </div>
        )}

        <div className="flex h-8 rounded-lg overflow-hidden mb-5 ring-1 ring-slate-200">
          {portfolio.weights.map(w => (
            <div key={w.asset_id}
              className={`${CATEGORY_COLOR_PUBLIC[w.category] ?? "bg-slate-400"}`}
              style={{ width: `${w.weight_pct}%` }}
              title={`${w.name}: ${w.weight_pct.toFixed(1)}%`} />
          ))}
        </div>

        <ul className="space-y-2.5">
          {portfolio.weights.map(w => (
            <li key={w.asset_id} className="flex items-center gap-3 text-sm py-1">
              <span className={`w-3 h-3 rounded-sm flex-shrink-0 ${CATEGORY_COLOR_PUBLIC[w.category] ?? "bg-slate-400"}`} />
              <span className="flex-1 text-slate-700">{w.name}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider">{w.category}</span>
              <span className="font-semibold text-navy w-16 text-right tabular-nums text-base">{w.weight_pct.toFixed(1)}%</span>
            </li>
          ))}
        </ul>

        {portfolio.note && (
          <div className="mt-5 pt-4 border-t border-slate-100">
            <p className="text-[11px] font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">담당 PB 코멘트</p>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{portfolio.note}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function Blank({ text }: { text: string }) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <p className="text-slate-400 text-sm">{text}</p>
    </div>
  );
}

const PRIORITY_LABEL: Record<string, { label: string; cls: string }> = {
  high:   { label: "1순위 검토", cls: "bg-gold text-white" },
  medium: { label: "2순위 검토", cls: "bg-blue-100 text-navy" },
  low:    { label: "참고",       cls: "bg-slate-100 text-slate-600" },
};

const KRW_FMT = new Intl.NumberFormat("ko-KR");

function TaxStrategySection({ strategy }: { strategy: NonNullable<Session["result"]["confirmed_tax_strategy"]> }) {
  const cands = strategy.candidates ?? [];
  const ranked = strategy.ranked ?? [];
  const rankMap = new Map(ranked.map(r => [r.product_id, r]));
  const order = { high: 0, medium: 1, low: 2 } as const;
  const sorted = [...cands].sort((a, b) => {
    const ap = (rankMap.get(a.product_id)?.priority ?? "low") as keyof typeof order;
    const bp = (rankMap.get(b.product_id)?.priority ?? "low") as keyof typeof order;
    return order[ap] - order[bp];
  });

  return (
    <div className="card-premium overflow-hidden mt-6">
      <div className="px-7 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-navy tracking-tight">추천 절세 플랜</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">담당 PB가 검토하여 확정한 절세 전략입니다.</p>
        </div>
        <span className="badge-confirmed text-[10px] px-2.5 py-0.5 rounded">확정</span>
      </div>

      <div className="px-7 py-6">
        {strategy.summary && (
          <div className="bg-gold-light/40 border-l-4 border-gold rounded px-4 py-3 mb-5 text-sm text-slate-700 leading-relaxed">
            {strategy.summary}
          </div>
        )}

        <ul className="space-y-3">
          {sorted.map(c => {
            const rk = rankMap.get(c.product_id);
            const ps = rk ? PRIORITY_LABEL[rk.priority] : PRIORITY_LABEL.low;
            if (!c.eligible) return null;
            return (
              <li key={c.product_id} className="border border-slate-200 rounded-lg p-4 hover:border-gold transition-colors">
                <div className="flex items-start justify-between gap-3 mb-1.5 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${ps.cls}`}>{ps.label}</span>
                    <span className="text-sm font-semibold text-slate-900">{c.name}</span>
                  </div>
                  {c.estimated_saving_won != null && (
                    <div className="text-right">
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider block">예상 절감</span>
                      <span className="text-sm font-bold text-gold tabular-nums">
                        {KRW_FMT.format(c.estimated_saving_won)}원/년
                      </span>
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-600 mb-1.5">{c.one_liner}</p>
                <p className="text-[11px] text-slate-500 mb-2">📐 {c.limit_text}</p>
                {rk && (
                  <p className="text-xs text-slate-700">
                    <span className="text-gold font-semibold">검토 사유 · </span>{rk.reason}
                  </p>
                )}
                {rk?.caveats && (
                  <p className="text-[11px] text-slate-500 mt-1">⚠ {rk.caveats}</p>
                )}
              </li>
            );
          })}
        </ul>

        {strategy.note && (
          <div className="mt-5 pt-4 border-t border-slate-100">
            <p className="text-[11px] font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">담당 PB 코멘트</p>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{strategy.note}</p>
          </div>
        )}

        <p className="mt-5 text-[10px] text-slate-400 leading-relaxed">
          본 자료는 담당 PB의 검토 결과를 안내하기 위한 자료이며 세무 자문이 아닙니다.
          실제 가입·매도 전 한도·자격·소득구간을 PB와 함께 다시 확인해 주시기 바랍니다.
        </p>
      </div>
    </div>
  );
}
