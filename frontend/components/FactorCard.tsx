"use client";
import type { FactorMeta, Flag } from "@/lib/api";

const CONFIDENCE_COLOR = { 상: "bg-green-100 text-green-800", 중: "bg-yellow-100 text-yellow-800", 하: "bg-red-100 text-red-800" } as const;
const STATUS_LABEL = { explicit: "명시", inferred: "추론", missing: "정보없음" } as const;

interface Props {
  title: string;
  factor: string;
  meta: FactorMeta;
  children?: React.ReactNode;
  inlineFlags?: Flag[];
}

export default function FactorCard({ title, factor, meta, children, inlineFlags = [] }: Props) {
  const isMissing = meta.status === "missing";
  const unresolvedRed = inlineFlags.filter(f => !f.resolved && f.severity === "red").length;

  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm ${unresolvedRed ? "border-red-400" : "border-gray-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-gray-800">{title}</span>
        <div className="flex gap-1.5 items-center">
          {meta.confidence && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_COLOR[meta.confidence]}`}>
              신뢰도 {meta.confidence}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full ${isMissing ? "bg-gray-100 text-gray-500" : "bg-blue-50 text-blue-700"}`}>
            {STATUS_LABEL[meta.status]}
          </span>
          {inlineFlags.length > 0 && <span className="text-sm">🔎</span>}
        </div>
      </div>

      {isMissing ? (
        <p className="text-sm text-gray-400 italic">정보 없음 — 추가 확인 필요</p>
      ) : (
        <div className="text-sm text-gray-700 space-y-1">
          {children}
          {meta.evidence && (
            <p className="text-xs text-gray-400 mt-1 border-l-2 border-gray-200 pl-2">근거: {meta.evidence}</p>
          )}
        </div>
      )}

      {inlineFlags.map(f => (
        <div key={f.rule_id} className={`mt-2 text-xs rounded px-2 py-1 ${f.resolved ? "bg-gray-50 text-gray-400 line-through" : f.severity === "red" ? "bg-red-50 text-red-700" : f.severity === "yellow" ? "bg-yellow-50 text-yellow-700" : "bg-gray-50 text-gray-500"}`}>
          [{f.rule_id}] {f.message}
        </div>
      ))}
    </div>
  );
}
