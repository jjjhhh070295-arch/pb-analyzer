"use client";
import { useEffect, useState } from "react";
import { use } from "react";
import { api, type Session } from "@/lib/api";

const fmtPct = (n: number | null) => n == null ? null : `${(n * 100).toFixed(0)}%`;
const fmtAmt = (n: number | null) =>
  n == null ? null : n >= 100000000 ? `${(n / 100000000).toFixed(1)}억` : `${(n / 10000).toLocaleString()}만`;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className="mt-1 sm:mt-0 sm:col-span-2 text-sm text-gray-900">{children}</dd>
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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-5">
        <p className="text-xs text-gray-400 mb-1">자산관리 분석 결과</p>
        <h1 className="text-2xl font-bold text-gray-900">{session.customer_name} 고객님</h1>
        <p className="text-sm text-gray-500 mt-0.5">상담일: {session.consult_date} · 담당 {session.pb_name}</p>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50">
            <h2 className="text-base font-semibold text-gray-700">투자 성향 분석 요약</h2>
          </div>
          <dl className="divide-y divide-gray-100 px-6">
            <Row label="목표 수익률">{returnStr}</Row>
            <Row label="위험 성향">{riskLevel ?? "미확인"}</Row>
            <Row label="투자 기간">
              {r.horizon.years != null ? `${r.horizon.years}년` : "미확인"}
            </Row>

            {(r.tax.items.length > 0 || r.tax.annual_financial_income != null) && (
              <Row label="세금 고려 사항">
                <ul className="space-y-0.5">
                  {r.tax.annual_financial_income != null && (
                    <li>연간 금융소득 {fmtAmt(r.tax.annual_financial_income)}</li>
                  )}
                  {r.tax.items.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </Row>
            )}

            {r.liquidity.events.length > 0 && (
              <Row label="유동성 계획">
                <ul className="space-y-0.5">
                  {r.liquidity.events.map((e, i) => (
                    <li key={i}>
                      {e.when && <span>{e.when}</span>}
                      {e.amount != null && <span className="ml-2">{fmtAmt(e.amount)}</span>}
                      {e.purpose && <span className="text-gray-500 ml-1">({e.purpose})</span>}
                    </li>
                  ))}
                </ul>
              </Row>
            )}

            {r.legal.items.length > 0 && (
              <Row label="법적 제약">
                <ul className="space-y-0.5">{r.legal.items.map((item, i) => <li key={i}>{item}</li>)}</ul>
              </Row>
            )}

            {(r.unique.notes.length > 0 || r.unique.excluded_sectors.length > 0) && (
              <Row label="기타 고려 사항">
                <ul className="space-y-0.5">
                  {r.unique.notes.map((n, i) => <li key={i}>{n}</li>)}
                  {r.unique.excluded_sectors.length > 0 && (
                    <li className="text-gray-500">배제 업종: {r.unique.excluded_sectors.join(", ")}</li>
                  )}
                </ul>
              </Row>
            )}
          </dl>
        </div>

        <p className="mt-6 text-xs text-center text-gray-400">
          본 자료는 참고용 분석 결과이며, 최종 투자 결정과 책임은 고객에게 있습니다.
        </p>
      </main>
    </div>
  );
}

function Blank({ text }: { text: string }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400 text-sm">{text}</div>
  );
}
