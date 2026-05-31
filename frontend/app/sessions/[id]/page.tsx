"use client";
import { useEffect, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { api, type Session } from "@/lib/api";
import FactorCard from "@/components/FactorCard";
import FlagList from "@/components/FlagList";
import FollowUpPanel from "@/components/FollowUpPanel";
import PortfolioTab from "@/components/PortfolioTab";

const fmt = (n: number | null) => n == null ? "—" : `${(n * 100).toFixed(0)}%`;
const fmtAmt = (n: number | null) => n == null ? "—" : `${(n / 100000000).toFixed(1)}억`;

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [session, setSession] = useState<Session | null>(null);
  const [activeTab, setActiveTab] = useState<"factors" | "flags" | "questions" | "portfolio">("factors");
  const [confirming, setConfirming] = useState(false);
  const [resolvingFlag, setResolvingFlag] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.sessions.get(id).then(s => {
      if ("result" in s) setSession(s as Session);
    });
  }, [id]);

  if (!session) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">불러오는 중…</div>;

  const r = session.result;
  const flags = r.flags ?? [];
  const unresolvedRed = flags.filter(f => !f.resolved && f.severity === "red").length;
  const inlineFlags = (factor: string) => flags.filter(f => f.inline_factor === factor);
  const confirmed = session.status === "확정";

  const confirm = async () => {
    if (unresolvedRed > 0) {
      setError(`미해결 빨간 플래그 ${unresolvedRed}개를 먼저 해소하세요.`);
      return;
    }
    setConfirming(true);
    try {
      await api.sessions.confirm(id);
      setSession(s => s ? { ...s, status: "확정" } : s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "확정 실패");
    } finally {
      setConfirming(false);
    }
  };

  const resolveFlag = async (ruleId: string) => {
    setResolvingFlag(ruleId);
    try {
      await api.sessions.resolveFlag(id, ruleId);
      setSession(s => {
        if (!s) return s;
        return { ...s, result: { ...s.result, flags: s.result.flags.map(f => f.rule_id === ruleId ? { ...f, resolved: true } : f) } };
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "해소 실패");
    } finally {
      setResolvingFlag(null);
    }
  };

  const unresolved = flags.filter(f => !f.resolved).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-gray-400 hover:text-gray-600 text-sm">← 목록</Link>
          <span className="text-xl font-bold text-gray-900">{session.customer_name} 상담 결과</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${confirmed ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
            {session.status}
          </span>
        </div>
        <div className="flex gap-2">
          {confirmed && (
            <Link href={`/customer/${id}`}
              className="border border-gray-300 text-gray-600 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
              고객 화면 보기 →
            </Link>
          )}
          {!confirmed && (
            <button onClick={confirm} disabled={confirming}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50">
              {confirming ? "처리 중…" : "✓ 검수 확정"}
            </button>
          )}
        </div>
      </header>

      {/* D-2 게이트: 미해결 빨간 플래그 경고 */}
      {unresolvedRed > 0 && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-3 text-sm text-red-700 flex items-center gap-2">
          🚨 미해결 빨간 플래그 {unresolvedRed}개 — 확정 전 반드시 확인하세요.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2 text-sm text-red-600">
          {error}
          <button onClick={() => setError("")} className="ml-2 underline text-xs">닫기</button>
        </div>
      )}

      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* 메타 정보 */}
        <div className="bg-white border border-gray-200 rounded-xl px-5 py-3 mb-5 text-sm text-gray-600 flex flex-wrap gap-4">
          <span>상담일: <strong>{session.consult_date}</strong></span>
          <span>담당 PB: <strong>{session.pb_name}</strong></span>
          <span>세션 ID: <span className="font-mono text-xs">{session.session_id}</span></span>
          {unresolved > 0 && <span className="ml-auto text-orange-600">미해결 플래그 {unresolved}개</span>}
        </div>

        {/* 탭 */}
        <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
          {(["factors", "flags", "questions", "portfolio"] as const).map(tab => {
            const labels = {
              factors: "7요인",
              flags: `플래그 (${unresolved})`,
              questions: `추가질문 (${r.follow_up_questions.length})`,
              portfolio: confirmed ? "📊 포트폴리오" : "포트폴리오",
            };
            return (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-md text-sm transition-colors ${activeTab === tab ? "bg-white shadow text-gray-900 font-medium" : "text-gray-500 hover:text-gray-700"}`}>
                {labels[tab]}
              </button>
            );
          })}
        </div>

        {/* 7요인 탭 */}
        {activeTab === "factors" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FactorCard title="목표수익률" factor="goal_return" meta={r.goal_return.meta} inlineFlags={inlineFlags("goal_return")}>
              {r.goal_return.raw_text && <p className="font-medium">{r.goal_return.raw_text}</p>}
              <p className="text-gray-500">{fmt(r.goal_return.return_min)} ~ {fmt(r.goal_return.return_max)}</p>
            </FactorCard>

            <FactorCard title="위험허용도" factor="risk_tolerance" meta={{ status: r.risk_tolerance.status as "explicit" | "inferred" | "missing", evidence: null, confidence: null }} inlineFlags={inlineFlags("risk_tolerance")}>
              <div className="space-y-1">
                <div className="flex justify-between"><span className="text-gray-500">의향</span><span>{r.risk_tolerance.willingness.level ?? "—"}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">능력</span><span>{r.risk_tolerance.capacity.level ?? "—"}</span></div>
                {r.risk_tolerance.binding && <div className="text-xs text-blue-600 mt-1">binding: {r.risk_tolerance.binding}</div>}
              </div>
            </FactorCard>

            <FactorCard title="투자 기간" factor="horizon" meta={r.horizon.meta} inlineFlags={inlineFlags("horizon")}>
              <p className="font-medium">{r.horizon.years != null ? `${r.horizon.years}년` : "—"}</p>
            </FactorCard>

            <FactorCard title="세금 요인" factor="tax" meta={r.tax.meta} inlineFlags={inlineFlags("tax")}>
              {r.tax.annual_financial_income != null && (
                <p>연 금융소득: <strong>{fmtAmt(r.tax.annual_financial_income)}</strong></p>
              )}
              {r.tax.items.length > 0 && (
                <ul className="mt-1 space-y-0.5">{r.tax.items.map((item, i) => <li key={i} className="text-gray-600">• {item}</li>)}</ul>
              )}
            </FactorCard>

            <FactorCard title="유동성 필요시기" factor="liquidity" meta={r.liquidity.meta} inlineFlags={inlineFlags("liquidity")}>
              {r.liquidity.events.length > 0 ? (
                <ul className="space-y-1">
                  {r.liquidity.events.map((e, i) => (
                    <li key={i} className="text-sm">
                      <span className="text-gray-500">{e.when}</span>
                      {e.amount != null && <span className="ml-2 font-medium">{fmtAmt(e.amount)}</span>}
                      {e.purpose && <span className="ml-2 text-gray-500">({e.purpose})</span>}
                    </li>
                  ))}
                </ul>
              ) : <p className="text-gray-400">이벤트 없음</p>}
            </FactorCard>

            <FactorCard title="법적 제약" factor="legal" meta={r.legal.meta} inlineFlags={inlineFlags("legal")}>
              {r.legal.items.length > 0
                ? <ul>{r.legal.items.map((item, i) => <li key={i}>• {item}</li>)}</ul>
                : <p className="text-gray-400">제약 없음</p>}
            </FactorCard>

            <FactorCard title="고유 상황" factor="unique" meta={r.unique.meta} inlineFlags={inlineFlags("unique")}>
              {r.unique.notes.length > 0 && <ul>{r.unique.notes.map((n, i) => <li key={i}>• {n}</li>)}</ul>}
              {r.unique.excluded_sectors.length > 0 && (
                <p className="text-xs text-orange-600 mt-1">배제 업종: {r.unique.excluded_sectors.join(", ")}</p>
              )}
            </FactorCard>
          </div>
        )}

        {/* 플래그 탭 */}
        {activeTab === "flags" && (
          <FlagList flags={flags} onResolve={confirmed ? undefined : resolveFlag} loading={resolvingFlag} />
        )}

        {/* 추가질문 탭 */}
        {activeTab === "questions" && (
          <FollowUpPanel questions={r.follow_up_questions} />
        )}

        {/* 포트폴리오 탭 */}
        {activeTab === "portfolio" && (
          <PortfolioTab sessionId={id} confirmed={confirmed} />
        )}
      </div>
    </div>
  );
}
