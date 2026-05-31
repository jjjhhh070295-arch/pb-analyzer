"use client";
import type { Flag } from "@/lib/api";

const SEV_STYLE = {
  red:    { dot: "●", row: "bg-red-50/70 border-red-200",       label: "🔴" },
  yellow: { dot: "●", row: "bg-amber-50/70 border-amber-200",   label: "🟡" },
  gray:   { dot: "●", row: "bg-slate-50 border-slate-200",      label: "⚪" },
};

interface Props {
  flags: Flag[];
  onResolve?: (ruleId: string) => void;
  loading?: string | null;
}

export default function FlagList({ flags, onResolve, loading }: Props) {
  if (flags.length === 0) {
    return (
      <div className="card-premium px-6 py-8 text-center">
        <p className="text-3xl mb-2">✓</p>
        <p className="text-sm text-slate-500">감지된 플래그가 없습니다.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {flags.map(f => {
        const s = SEV_STYLE[f.severity];
        return (
          <li key={f.rule_id} className={`flex items-start gap-3 border rounded-lg px-3.5 py-2.5 ${f.resolved ? "opacity-40 bg-white border-slate-200" : s.row}`}>
            <span className="mt-0.5 text-base">{s.label}</span>
            <div className="flex-1 min-w-0">
              <span className="text-[11px] font-mono text-slate-500 mr-1.5 font-semibold">{f.rule_id}</span>
              <span className={`text-sm ${f.resolved ? "line-through text-slate-400" : "text-slate-800"}`}>{f.message}</span>
              {f.inline_factor && <span className="ml-2 text-[11px] text-slate-400">({f.inline_factor})</span>}
            </div>
            {!f.resolved && onResolve && (
              <button
                onClick={() => onResolve(f.rule_id)}
                disabled={loading === f.rule_id}
                className="text-xs text-slate-400 hover:text-gold transition-colors whitespace-nowrap disabled:opacity-50 font-medium"
              >
                {loading === f.rule_id ? "처리중…" : "해소"}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
