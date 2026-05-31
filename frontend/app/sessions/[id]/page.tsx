"use client";
import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Session, type AnalysisResult } from "@/lib/api";
import FactorCard from "@/components/FactorCard";
import FlagList from "@/components/FlagList";
import FollowUpPanel from "@/components/FollowUpPanel";
import PortfolioTab from "@/components/PortfolioTab";
import EditFactorsModal from "@/components/EditFactorsModal";

const fmt = (n: number | null) => n == null ? "—" : `${(n * 100).toFixed(0)}%`;
const fmtAmt = (n: number | null) => n == null ? "—" : `${(n / 100000000).toFixed(1)}억`;

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [activeTab, setActiveTab] = useState<"factors" | "flags" | "questions" | "portfolio">("factors");
  const [confirming, setConfirming] = useState(false);
  const [resolvingFlag, setResolvingFlag] = useState<string | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const refetch = async () => {
    const s = await api.sessions.get(id);
    if ("result" in s) setSession(s as Session);
  };

  useEffect(() => { refetch(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);

  if (!session) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400 text-sm">
        불러오는 중…
      </div>
    );
  }

  const r = session.result;
  const flags = r.flags ?? [];
  const unresolvedRed = flags.filter(f => !f.resolved && f.severity === "red").length;
  const unresolved = flags.filter(f => !f.resolved).length;
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
      await refetch();
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
      setSession(s => s ? { ...s, result: { ...s.result, flags: s.result.flags.map(f => f.rule_id === ruleId ? { ...f, resolved: true } : f) } } : s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "해소 실패");
    } finally {
      setResolvingFlag(null);
    }
  };

  // 추가질문 답변 → 재분석. 확정 상태에서는 자동으로 검수중으로 되돌림(서버가 처리).
  const submitAnswers = async (combined: string) => {
    setReanalyzing(true);
    setError("");
    try {
      await api.sessions.reanalyze(id, { additional_text: combined });
      // 폴링
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const s = await api.sessions.getStatus(id);
        if (s.status === "done") {
          await refetch();
          setActiveTab("factors");
          return;
        }
        if (s.status === "error") {
          setError(s.error ?? "재분석 오류");
          return;
        }
      }
      setError("재분석 시간 초과");
    } catch (e) {
      setError(e instanceof Error ? e.message : "재분석 실패");
    } finally {
      setReanalyzing(false);
    }
  };

  // 7요인 직접 편집 저장
  const saveEdited = async (next: AnalysisResult) => {
    try {
      await api.sessions.updateResult(id, next);
      await refetch();
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    }
  };

  const deleteSession = async () => {
    setDeleting(true);
    try {
      await api.sessions.delete(id);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  // 확정 후 PB가 다시 수정하고 싶을 때 → 검수중 상태로 되돌리기 (재분석 안 함)
  const revertToDraft = async () => {
    setReanalyzing(true);
    try {
      // raw_text 그대로 재분석 = 사실상 상태만 검수중으로 변경되는 효과
      await api.sessions.reanalyze(id, { additional_text: "" });
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const s = await api.sessions.getStatus(id);
        if (s.status === "done") { await refetch(); return; }
        if (s.status === "error") { setError(s.error ?? "오류"); return; }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "재수정 진입 실패");
    } finally {
      setReanalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-header-gradient text-white">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/" className="text-blue-100 hover:text-gold text-xs font-medium whitespace-nowrap">← 목록</Link>
            <span className="text-blue-200">|</span>
            <div className="min-w-0">
              <h1 className="text-lg font-bold tracking-tight truncate">{session.customer_name} 고객 상담 분석</h1>
              <p className="text-blue-100 text-xs mt-0.5">{session.consult_date} · 담당 {session.pb_name} · <span className="font-mono">{session.session_id}</span></p>
            </div>
            {confirmed
              ? <span className="badge-confirmed text-[10px] px-2.5 py-0.5 rounded shrink-0">확정</span>
              : <span className="bg-white/15 text-white text-[10px] px-2.5 py-0.5 rounded shrink-0 font-medium">검수중</span>}
          </div>
          <div className="flex gap-2 shrink-0 items-center">
            {!confirmed && (
              <button onClick={() => setEditing(true)}
                className="border border-blue-100/40 text-white px-3 py-1.5 rounded-lg text-xs hover:bg-white/10 transition-colors">
                ✎ 7요인 편집
              </button>
            )}
            {confirmed ? (
              <>
                <button onClick={revertToDraft} disabled={reanalyzing}
                  className="border border-blue-100/40 text-white px-3 py-1.5 rounded-lg text-xs hover:bg-white/10 transition-colors disabled:opacity-50">
                  {reanalyzing ? "처리중…" : "재수정 모드"}
                </button>
                <Link href={`/customer/${id}`}
                  className="bg-white text-navy px-4 py-1.5 rounded-lg text-xs font-medium hover:bg-gold hover:text-white transition-colors">
                  고객 화면 보기 →
                </Link>
              </>
            ) : (
              <button onClick={confirm} disabled={confirming}
                className="btn-gold px-5 py-2 rounded-lg text-sm shadow-md">
                {confirming ? "처리 중…" : "✓ 검수 확정"}
              </button>
            )}
            <button onClick={() => setConfirmDelete(true)} title="이 상담 삭제"
              className="text-blue-100 hover:text-red-300 transition-colors px-2 py-1.5 text-sm">
              🗑
            </button>
          </div>
        </div>
        <div className="gold-accent-line" />
      </header>

      {unresolvedRed > 0 && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2.5 text-sm text-red-700">
          🚨 미해결 빨간 플래그 {unresolvedRed}개 — 확정 전 반드시 확인하세요.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2 text-sm text-red-600 flex items-center">
          <span>{error}</span>
          <button onClick={() => setError("")} className="ml-3 underline text-xs">닫기</button>
        </div>
      )}

      {reanalyzing && (
        <div className="bg-blue-50 border-b border-blue-200 px-6 py-2.5 text-sm text-navy flex items-center gap-2">
          <span className="animate-spin">⏳</span> 재분석 중… 잠시만 기다려주세요.
        </div>
      )}

      <div className="max-w-5xl mx-auto px-6 py-7">
        <div className="flex items-center gap-1 mb-5 bg-white border border-slate-200 rounded-xl p-1 w-fit shadow-sm">
          {(["factors", "flags", "questions", "portfolio"] as const).map(tab => {
            const labels = {
              factors: "7요인",
              flags: `플래그${unresolved > 0 ? ` · ${unresolved}` : ""}`,
              questions: `추가질문${r.follow_up_questions.length > 0 ? ` · ${r.follow_up_questions.length}` : ""}`,
              portfolio: "포트폴리오",
            };
            const isActive = activeTab === tab;
            return (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-lg text-sm transition-colors ${isActive ? "bg-navy text-white font-medium shadow-sm" : "text-slate-500 hover:text-navy"}`}>
                {labels[tab]}
              </button>
            );
          })}
        </div>

        {/* 7요인 탭 */}
        {activeTab === "factors" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FactorCard title="목표수익률" meta={r.goal_return.meta} inlineFlags={inlineFlags("goal_return")}>
              {r.goal_return.raw_text && <p className="font-semibold text-navy">{r.goal_return.raw_text}</p>}
              <p className="text-slate-500 text-xs">{fmt(r.goal_return.return_min)} ~ {fmt(r.goal_return.return_max)}</p>
            </FactorCard>

            <FactorCard title="위험허용도"
              meta={{ status: r.risk_tolerance.status as "explicit" | "inferred" | "missing", evidence: null, confidence: null }}
              inlineFlags={inlineFlags("risk_tolerance")}>
              <div className="space-y-1">
                <div className="flex justify-between"><span className="text-slate-500 text-xs">의향</span><span className="font-medium">{r.risk_tolerance.willingness.level ?? "—"}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 text-xs">능력</span><span className="font-medium">{r.risk_tolerance.capacity.level ?? "—"}</span></div>
                {r.risk_tolerance.binding && (
                  <div className="text-[10px] text-gold mt-1 font-semibold tracking-wide">
                    BINDING: {r.risk_tolerance.binding === "willingness" ? "의향" : "능력"}
                  </div>
                )}
              </div>
            </FactorCard>

            <FactorCard title="투자 기간" meta={r.horizon.meta} inlineFlags={inlineFlags("horizon")}>
              <p className="font-semibold text-navy">{r.horizon.years != null ? `${r.horizon.years}년` : "—"}</p>
            </FactorCard>

            <FactorCard title="세금 요인" meta={r.tax.meta} inlineFlags={inlineFlags("tax")}>
              {r.tax.annual_financial_income != null && (
                <p>연 금융소득 <span className="font-semibold text-navy">{fmtAmt(r.tax.annual_financial_income)}</span></p>
              )}
              {r.tax.items.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs">{r.tax.items.map((item, i) => <li key={i} className="text-slate-600">• {item}</li>)}</ul>
              )}
            </FactorCard>

            <FactorCard title="유동성 필요시기" meta={r.liquidity.meta} inlineFlags={inlineFlags("liquidity")}>
              {r.liquidity.events.length > 0 ? (
                <ul className="space-y-1">
                  {r.liquidity.events.map((e, i) => (
                    <li key={i} className="text-sm">
                      <span className="text-slate-500 text-xs">{e.when}</span>
                      {e.amount != null && <span className="ml-2 font-semibold text-navy">{fmtAmt(e.amount)}</span>}
                      {e.purpose && <span className="ml-2 text-slate-500 text-xs">({e.purpose})</span>}
                    </li>
                  ))}
                </ul>
              ) : <p className="text-slate-400 text-xs">단기 유동성 필요 없음</p>}
            </FactorCard>

            <FactorCard title="법적 제약" meta={r.legal.meta} inlineFlags={inlineFlags("legal")}>
              {r.legal.items.length > 0
                ? <ul className="text-xs space-y-0.5">{r.legal.items.map((item, i) => <li key={i}>• {item}</li>)}</ul>
                : <p className="text-slate-400 text-xs">제약 없음</p>}
            </FactorCard>

            <FactorCard title="고유 상황" meta={r.unique.meta} inlineFlags={inlineFlags("unique")}>
              {r.unique.notes.length > 0 && <ul className="text-xs space-y-0.5">{r.unique.notes.map((n, i) => <li key={i}>• {n}</li>)}</ul>}
              {r.unique.excluded_sectors.length > 0 && (
                <p className="text-[11px] text-gold mt-1.5 font-semibold tracking-wide">배제 업종: {r.unique.excluded_sectors.join(", ")}</p>
              )}
            </FactorCard>
          </div>
        )}

        {activeTab === "flags" && (
          <FlagList flags={flags} onResolve={confirmed ? undefined : resolveFlag} loading={resolvingFlag} />
        )}

        {activeTab === "questions" && (
          <FollowUpPanel
            questions={r.follow_up_questions}
            onSubmit={submitAnswers}
            submitting={reanalyzing}
          />
        )}

        {activeTab === "portfolio" && (
          <PortfolioTab sessionId={id} confirmed={confirmed} />
        )}
      </div>

      {editing && (
        <EditFactorsModal
          result={r}
          onClose={() => setEditing(false)}
          onSave={saveEdited}
        />
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-xl w-full max-w-sm p-6 shadow-2xl">
            <p className="text-base font-bold text-slate-900 mb-2">상담 삭제</p>
            <p className="text-sm text-slate-600 mb-5 leading-relaxed">
              <strong className="text-navy">{session.customer_name}</strong> 고객의 <span className="font-mono text-xs">{session.session_id}</span> 상담을 완전히 삭제합니다. 되돌릴 수 없습니다.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(false)} disabled={deleting}
                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">취소</button>
              <button onClick={deleteSession} disabled={deleting}
                className="bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50">
                {deleting ? "삭제 중…" : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
