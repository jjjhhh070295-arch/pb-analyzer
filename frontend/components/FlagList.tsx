"use client";
import type { Flag } from "@/lib/api";

const SEV_STYLE = {
  red: { dot: "bg-red-500", row: "bg-red-50 border-red-200", label: "🔴" },
  yellow: { dot: "bg-yellow-400", row: "bg-yellow-50 border-yellow-200", label: "🟡" },
  gray: { dot: "bg-gray-400", row: "bg-gray-50 border-gray-200", label: "⚪" },
};

interface Props {
  flags: Flag[];
  onResolve?: (ruleId: string) => void;
  loading?: string | null;
}

export default function FlagList({ flags, onResolve, loading }: Props) {
  if (flags.length === 0) return <p className="text-sm text-gray-400">플래그 없음</p>;

  return (
    <ul className="space-y-2">
      {flags.map(f => {
        const s = SEV_STYLE[f.severity];
        return (
          <li key={f.rule_id} className={`flex items-start gap-3 border rounded-lg px-3 py-2 ${f.resolved ? "opacity-40" : s.row}`}>
            <span className="mt-1 text-base">{s.label}</span>
            <div className="flex-1 min-w-0">
              <span className="text-xs font-mono text-gray-500 mr-1">[{f.rule_id}]</span>
              <span className={`text-sm ${f.resolved ? "line-through" : ""}`}>{f.message}</span>
              {f.inline_factor && <span className="ml-2 text-xs text-gray-400">({f.inline_factor})</span>}
            </div>
            {!f.resolved && onResolve && (
              <button
                onClick={() => onResolve(f.rule_id)}
                disabled={loading === f.rule_id}
                className="text-xs text-gray-400 hover:text-green-600 whitespace-nowrap disabled:opacity-50"
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
