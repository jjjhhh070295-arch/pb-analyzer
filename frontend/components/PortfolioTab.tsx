"use client";
import { useState } from "react";
import { api, type PortfolioResult } from "@/lib/api";

const CATEGORY_COLOR: Record<string, string> = {
  "국내주식": "bg-blue-500",
  "해외주식": "bg-indigo-500",
  "리츠":    "bg-purple-400",
  "원자재":  "bg-amber-400",
  "달러":    "bg-green-400",
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
    return <p className="text-sm text-gray-400">PB 검수 확정 후 포트폴리오 최적화를 실행할 수 있습니다.</p>;
  }

  if (!result && !loading) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500 text-sm mb-4">7요인 제약 → 리스크 패리티 포트폴리오 최적화</p>
        <button onClick={run}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm hover:bg-blue-700">
          최적화 실행
        </button>
        <p className="text-xs text-gray-400 mt-2">실시간 가격 데이터 수집 포함 · 약 10~30초</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p className="text-2xl mb-2 animate-spin inline-block">⏳</p>
        <p className="text-sm">시장 데이터 수집 및 최적화 중…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500 text-sm mb-3">{error}</p>
        <button onClick={run} className="text-blue-600 text-sm underline">재시도</button>
      </div>
    );
  }

  if (!result) return null;

  const m = result.metrics;
  const riskColor = m.downside_risk_score < 33 ? "text-green-600" : m.downside_risk_score < 66 ? "text-yellow-600" : "text-red-600";

  return (
    <div className="space-y-5">
      {result.provisional && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-2 text-sm text-yellow-700">
          ⚠ 핵심 요인 신뢰도가 낮아 잠정 결과입니다. 추가 정보 확인 후 재실행을 권장합니다.
        </div>
      )}
      {result.warnings.map((w, i) => (
        <div key={i} className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-2 text-sm text-orange-700">{w}</div>
      ))}

      {/* 핵심 지표 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard label="기대수익률" value={`${m.expected_return_pct.toFixed(1)}%`} sub="연환산" color="text-blue-600" />
        <MetricCard label="위험 점수" value={`${m.downside_risk_score.toFixed(0)}/100`} sub="하방변동성 기준" color={riskColor} />
        <MetricCard label="소르티노" value={m.sortino_ratio.toFixed(2)} sub="위험조정 성과" color="text-purple-600" />
        <MetricCard label="베타 (vs SPY)" value={m.beta.toFixed(2)} sub="시장 민감도" color="text-gray-700" />
      </div>

      {/* 자산 배분 */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <p className="text-sm font-semibold text-gray-700 mb-3">자산 배분</p>

        {/* 막대 그래프 */}
        <div className="flex h-6 rounded-lg overflow-hidden mb-3">
          {result.weights.map(w => (
            <div key={w.asset_id}
              className={`${CATEGORY_COLOR[w.category] ?? "bg-gray-400"} transition-all`}
              style={{ width: `${w.weight_pct}%` }}
              title={`${w.name}: ${w.weight_pct}%`} />
          ))}
        </div>

        {/* 범례 */}
        <ul className="space-y-1.5">
          {result.weights.map(w => (
            <li key={w.asset_id} className="flex items-center gap-2 text-sm">
              <span className={`w-3 h-3 rounded-sm flex-shrink-0 ${CATEGORY_COLOR[w.category] ?? "bg-gray-400"}`} />
              <span className="flex-1 text-gray-700">{w.name}</span>
              <span className="font-medium text-gray-900 w-12 text-right">{w.weight_pct.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex justify-end">
        <button onClick={run} className="text-xs text-gray-400 hover:text-gray-600 underline">
          재실행
        </button>
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
