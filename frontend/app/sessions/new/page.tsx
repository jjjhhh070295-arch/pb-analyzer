"use client";
import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

function NewSessionForm() {
  const router = useRouter();
  const params = useSearchParams();
  const customerId = params.get("customer_id") ?? "";
  const pbName = params.get("pb_name") ?? "";

  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "polling">("idle");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setError("");
    setStatus("submitting");

    try {
      const { session_id } = await api.sessions.start({
        customer_id: customerId, pb_name: pbName, raw_text: text,
      });
      setStatus("polling");
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const s = await api.sessions.getStatus(session_id);
        if (s.status === "done") { router.push(`/sessions/${session_id}`); return; }
        if (s.status === "error") { setError(s.error ?? "분석 중 오류"); setStatus("idle"); return; }
      }
      setError("분석 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.");
      setStatus("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류 발생");
      setStatus("idle");
    }
  };

  const busy = status !== "idle";

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-header-gradient text-white">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center gap-3">
          <Link href="/" className="text-blue-100 hover:text-gold text-xs font-medium">← 목록</Link>
          <span className="text-blue-200">|</span>
          <h1 className="text-lg font-bold tracking-tight">새 상담 분석</h1>
        </div>
        <div className="gold-accent-line" />
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="card-premium px-5 py-3 mb-5 text-sm text-slate-600 flex items-center gap-3">
          <span className="font-mono text-[11px] text-slate-400 tracking-wider">{customerId}</span>
          <span className="text-slate-300">|</span>
          <span>담당 PB: <span className="font-semibold text-navy">{pbName || "—"}</span></span>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wider">고객 상담 원문</label>
            <textarea
              required value={text} onChange={e => setText(e.target.value)}
              disabled={busy} rows={12}
              placeholder="고객과 나눈 상담 내용을 자유롭게 입력하세요.&#10;예) 연 7~9% 수익을 원하고, 손실은 최대 20% 정도까지 감내 가능합니다. 5년 정도 투자 가능하며…"
              className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 resize-none bg-white disabled:bg-slate-50"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {status === "polling" && (
            <div className="flex items-center gap-2 text-sm text-navy bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5">
              <span className="animate-spin">⏳</span> 7요인 분석 중… (최대 30초 소요)
            </div>
          )}

          <button type="submit" disabled={busy}
            className="btn-navy w-full py-3.5 rounded-lg text-sm shadow-md">
            {status === "submitting" ? "요청 중…" : status === "polling" ? "분석 중…" : "분석 시작"}
          </button>
        </form>
      </main>
    </div>
  );
}

export default function NewSessionPage() {
  return <Suspense><NewSessionForm /></Suspense>;
}
