"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Customer, type Session } from "@/lib/api";

export default function Home() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([api.customers.list(), api.sessions.list()])
      .then(([c, s]) => { setCustomers(c); setSessions(s); })
      .finally(() => setLoading(false));
  }, []);

  const filtered = customers.filter(c =>
    c.name.includes(search) || c.customer_id.includes(search)
  );

  const latestSession = (customerId: string) =>
    sessions
      .filter(s => s.customer_id === customerId)
      .sort((a, b) => b.consult_datetime.localeCompare(a.consult_datetime))[0];

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-header-gradient text-white">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">PB Wealth Analyzer</h1>
              <span className="text-gold text-xs font-semibold tracking-widest">PRIVATE</span>
            </div>
            <p className="text-blue-100 text-xs mt-0.5">고액자산가 상담 분석 시스템</p>
          </div>
          <Link href="/customers/new"
            className="btn-gold px-5 py-2 rounded-lg text-sm shadow-md">
            + 신규 고객 등록
          </Link>
        </div>
        <div className="gold-accent-line" />
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-6">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="고객명 또는 ID로 검색…"
            className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-900/20 focus:border-blue-900"
          />
        </div>

        {loading ? (
          <p className="text-slate-400 text-center py-12">불러오는 중…</p>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <p className="text-4xl mb-3">👤</p>
            <p>등록된 고객이 없습니다.</p>
            <Link href="/customers/new" className="mt-4 inline-block text-navy text-sm font-medium hover:underline">고객 등록하기 →</Link>
          </div>
        ) : (
          <ul className="space-y-3">
            {filtered.map(c => {
              const latest = latestSession(c.customer_id);
              const confirmed = latest?.status === "확정";
              return (
                <li key={c.customer_id} className="card-premium px-6 py-5 flex items-center justify-between transition-all">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5 mb-1">
                      <span className="font-semibold text-slate-900 text-base">{c.name}</span>
                      <span className="text-[11px] text-slate-400 font-mono tracking-wider">{c.customer_id}</span>
                      {latest && (
                        confirmed ? (
                          <span className="badge-confirmed text-[10px] px-2 py-0.5 rounded">확정</span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">검수중</span>
                        )
                      )}
                    </div>
                    <div className="text-xs text-slate-500">
                      <span>{c.birth_date}</span>
                      <span className="mx-2 text-slate-300">·</span>
                      <span>담당 {c.primary_pb}</span>
                      {latest && <>
                        <span className="mx-2 text-slate-300">·</span>
                        <span>최근 상담 {latest.consult_date}</span>
                      </>}
                    </div>
                  </div>
                  <div className="flex gap-4 ml-4 shrink-0 items-center">
                    <Link href={`/sessions/new?customer_id=${c.customer_id}&pb_name=${encodeURIComponent(c.primary_pb)}`}
                      className="text-sm text-navy font-medium hover:text-gold transition-colors">새 상담</Link>
                    {latest && (
                      <>
                        <Link href={`/sessions/${latest.session_id}`}
                          className="text-sm text-slate-500 hover:text-navy transition-colors">결과 보기</Link>
                        <button
                          onClick={async () => {
                            if (!confirm(`${c.name} 고객의 최근 상담(${latest.session_id})을 삭제하시겠습니까?`)) return;
                            try {
                              await api.sessions.delete(latest.session_id);
                              setSessions(prev => prev.filter(s => s.session_id !== latest.session_id));
                            } catch (e) {
                              alert(e instanceof Error ? e.message : "삭제 실패");
                            }
                          }}
                          title="최근 상담만 삭제"
                          className="text-slate-300 hover:text-amber-600 transition-colors text-sm">
                          🗑
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => setDeleteTarget(c)}
                      title="고객 완전 삭제 (모든 상담 포함)"
                      className="text-slate-300 hover:text-red-500 transition-colors text-sm border-l border-slate-200 pl-3">
                      ✕
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>

      <footer className="max-w-5xl mx-auto px-6 py-8 text-center">
        <p className="text-[11px] text-slate-400 tracking-wide">© PB Wealth Analyzer · 분석 결과는 참고용이며 최종 투자 판단은 PB에게 있습니다</p>
      </footer>

      {deleteTarget && (() => {
        const linkedCount = sessions.filter(s => s.customer_id === deleteTarget.customer_id).length;
        const confirmDelete = async () => {
          setDeleting(true);
          try {
            await api.customers.delete(deleteTarget.customer_id);
            setCustomers(prev => prev.filter(c => c.customer_id !== deleteTarget.customer_id));
            setSessions(prev => prev.filter(s => s.customer_id !== deleteTarget.customer_id));
            setDeleteTarget(null);
          } catch (e) {
            alert(e instanceof Error ? e.message : "삭제 실패");
          } finally {
            setDeleting(false);
          }
        };
        return (
          <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4 backdrop-blur-sm">
            <div className="bg-white rounded-xl w-full max-w-sm p-6 shadow-2xl">
              <p className="text-base font-bold text-slate-900 mb-2">고객 완전 삭제</p>
              <p className="text-sm text-slate-600 mb-1 leading-relaxed">
                <strong className="text-navy">{deleteTarget.name}</strong> <span className="text-xs text-slate-400 font-mono">({deleteTarget.customer_id})</span> 고객을 완전히 삭제합니다.
              </p>
              {linkedCount > 0 && (
                <p className="text-sm text-red-600 mb-3 font-medium">
                  ⚠ 연결된 상담 {linkedCount}건도 함께 삭제됩니다.
                </p>
              )}
              <p className="text-xs text-slate-400 mb-5">되돌릴 수 없습니다.</p>
              <div className="flex justify-end gap-2">
                <button onClick={() => setDeleteTarget(null)} disabled={deleting}
                  className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">취소</button>
                <button onClick={confirmDelete} disabled={deleting}
                  className="bg-red-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50">
                  {deleting ? "삭제 중…" : "고객 + 상담 모두 삭제"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
