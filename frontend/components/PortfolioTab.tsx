"use client";
import { useState } from "react";
import { api, type PortfolioResult } from "@/lib/api";

const CATEGORY_COLOR: Record<string, string> = {
  "국내주식": "bg-blue-900",
  "해외주식": "bg-blue-700",
  "리츠":    "bg-indigo-500",
  "원자재":  "bg-amber-500",
  "달러":    "bg-amber-300",
};

interface Props {
  sessionId: string;
  confirmed: boolean;
}

export default function PortfolioTab({ sessionId, confirmed }: Props) {
  const [result, setResult] = useState<PortfolioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await api.portfolio.optimize(sessionId);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "최적화 실패");
    } finally {
      setLoading(false);
    }
  };

  if (!confirmed) {
    return (
      <div className="card-premium px-6 py-8 text-center text-sm text-slate-500">
        PB 검수 확정 후 포트폴리오 최적화를 실행할 수 있습니다.
      </div>
    );
  }

  if (!result && !loading) {
    return (
      <div className="card-premium px-6 py-12 text-center">
        <p className="text-3xl mb-3">📊</p>
        <p className="text-sm text-slate-600 mb-1 font-medium">리스크 패리티 포트폴리오 최적화</p>
        <p className="text-xs text-slate-400 mb-5">7요인 제약을 바탕으로 자산 배분을 산출합니다</p>
        <button onClick={run}
          className="btn-navy px-7 py-2.5 rounded-lg text-sm shadow-sm">
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

  if (error) {
    return (
      <div className="card-premium px-6 py-8 text-center">
        <p className="text-red-500 text-sm mb-3">{error}</p>
        <button onClick={run} className="text-navy text-sm font-medium hover:underline">재시도</button>
      </div>
    );
  }

  if (!result) return null;

  const m = result.metrics;
  const riskTone = m.downside_risk_score < 33 ? "text-emerald-700" : m.downside_risk_score < 66 ? "text-amber-700" : "text-red-700";

  return (
    <div className="space-y-5">
      {result.provisional && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          ⚠ 핵심 요인 신뢰도가 낮아 잠정 결과입니다. 추가 정보 확인 후 재실행을 권장합니다.
        </div>
      )}
      {result.warnings.map((w, i) => (
        <div key={i} className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-2.5 text-sm text-orange-800">{w}</div>
      ))}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="기대수익률" value={`${m.expected_return_pct.toFixed(1)}%`} sub="연환산" valueColor="text-navy" />
        <MetricCard label="위험 점수" value={`${m.downside_risk_score.toFixed(0)}/100`} sub="하방변동성" valueColor={riskTone} />
        <MetricCard label="소르티노" value={m.sortino_ratio.toFixed(2)} sub="위험조정 성과" valueColor="text-gold" />
        <MetricCard label="베타" value={m.beta.toFixed(2)} sub="vs S&P 500" valueColor="text-slate-700" />
      </div>

      <div className="card-premium p-5">
        <p className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-2">
          <span className="w-1 h-4 bg-gold rounded-sm" />
          자산 배분
        </p>

        <div className="flex h-7 rounded-lg overflow-hidden mb-4 ring-1 ring-slate-200">
          {result.weights.map(w => (
            <div key={w.asset_id}
              className={`${CATEGORY_COLOR[w.category] ?? "bg-slate-400"} transition-all`}
              style={{ width: `${w.weight_pct}%` }}
              title={`${w.name}: ${w.weight_pct}%`} />
          ))}
        </div>

        <ul className="space-y-2">
          {result.weights.map(w => (
            <li key={w.asset_id} className="flex items-center gap-3 text-sm">
              <span className={`w-2.5 h-2.5 rounded-sm flex-shrink-0 ${CATEGORY_COLOR[w.category] ?? "bg-slate-400"}`} />
              <span className="flex-1 text-slate-700">{w.name}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider w-16">{w.category}</span>
              <span className="font-semibold text-slate-900 w-14 text-right tabular-nums">{w.weight_pct.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex justify-end">
        <button onClick={run} className="text-xs text-slate-400 hover:text-navy underline transition-colors">
          최적화 재실행
        </button>
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
