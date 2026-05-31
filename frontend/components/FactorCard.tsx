"use client";
import type { FactorMeta, Flag } from "@/lib/api";

const CONFIDENCE_COLOR = {
  상: "bg-gold-light text-amber-900 border border-amber-200",
  중: "bg-slate-100 text-slate-700 border border-slate-200",
  하: "bg-red-50 text-red-700 border border-red-200",
} as const;

const STATUS_LABEL = { explicit: "명시", inferred: "추론", missing: "정보없음" } as const;
const STATUS_STYLE = {
  explicit: "bg-blue-50 text-navy",
  inferred: "bg-slate-100 text-slate-600",
  missing: "bg-slate-50 text-slate-400",
} as const;

interface Props {
  title: string;
  meta: FactorMeta;
  children?: React.ReactNode;
  inlineFlags?: Flag[];
}

export default function FactorCard({ title, meta, children, inlineFlags = [] }: Props) {
  const isMissing = meta.status === "missing";
  const unresolvedRed = inlineFlags.filter(f => !f.resolved && f.severity === "red").length;

  return (
    <div className={`card-premium p-5 ${unresolvedRed ? "ring-1 ring-red-300" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-slate-900 text-sm tracking-tight">{title}</span>
        <div className="flex gap-1.5 items-center">
          {meta.confidence && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_COLOR[meta.confidence]}`}>
              {meta.confidence}
            </span>
          )}
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${STATUS_STYLE[meta.status]}`}>
            {STATUS_LABEL[meta.status]}
          </span>
          {inlineFlags.length > 0 && <span className="text-sm">🔎</span>}
        </div>
      </div>

      {isMissing ? (
        <p className="text-sm text-slate-400 italic">정보 없음 — 추가 확인 필요</p>
      ) : (
        <div className="text-sm text-slate-700 space-y-1">
          {children}
          {meta.evidence && (
            <p className="text-[11px] text-slate-400 mt-2 border-l-2 border-gold pl-2 leading-relaxed">
              {meta.evidence}
            </p>
          )}
        </div>
      )}

      {inlineFlags.map(f => (
        <div key={f.rule_id} className={`mt-2 text-xs rounded px-2 py-1 ${f.resolved ? "bg-slate-50 text-slate-400 line-through" : f.severity === "red" ? "bg-red-50 text-red-700" : f.severity === "yellow" ? "bg-amber-50 text-amber-800" : "bg-slate-50 text-slate-500"}`}>
          [{f.rule_id}] {f.message}
        </div>
      ))}
    </div>
  );
}
