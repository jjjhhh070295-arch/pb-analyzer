"use client";
import { useState } from "react";

interface Props {
  questions: string[];
  onSubmit?: (combinedAnswer: string) => Promise<void> | void;
  submitting?: boolean;
  disabled?: boolean;
}

export default function FollowUpPanel({ questions, onSubmit, submitting, disabled }: Props) {
  const [answers, setAnswers] = useState<Record<number, string>>({});

  if (questions.length === 0) {
    return (
      <div className="card-premium px-6 py-8 text-center">
        <p className="text-3xl mb-2">✓</p>
        <p className="text-sm text-slate-500">추가 확인이 필요한 질문이 없습니다.</p>
      </div>
    );
  }

  const filled = Object.values(answers).filter(v => v.trim()).length;
  const setAns = (i: number, v: string) => setAnswers(a => ({ ...a, [i]: v }));

  const submit = () => {
    if (!onSubmit) return;
    const merged = questions
      .map((q, i) => answers[i]?.trim() ? `Q. ${q}\nA. ${answers[i].trim()}` : null)
      .filter(Boolean)
      .join("\n\n");
    if (!merged) return;
    onSubmit(merged);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-200 bg-blue-50/60 px-4 py-3">
        <p className="text-sm font-semibold text-navy mb-1">📋 추가 확인이 필요한 항목 ({questions.length})</p>
        <p className="text-xs text-slate-500">고객으로부터 받은 답변을 입력하고 ‘답변 반영 후 재분석’을 누르면 분석이 갱신됩니다.</p>
      </div>

      <ol className="space-y-4">
        {questions.map((q, i) => (
          <li key={i} className="card-premium p-4">
            <div className="flex gap-2 mb-2">
              <span className="text-xs font-mono text-gold font-semibold mt-0.5">{String(i + 1).padStart(2, "0")}</span>
              <p className="text-sm text-slate-800 flex-1">{q}</p>
            </div>
            <textarea
              value={answers[i] ?? ""}
              onChange={e => setAns(i, e.target.value)}
              disabled={disabled || submitting}
              rows={2}
              placeholder="고객 답변을 입력하세요…"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 resize-none disabled:bg-slate-100"
            />
          </li>
        ))}
      </ol>

      {onSubmit && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-slate-500">{filled} / {questions.length} 답변 작성됨</p>
          <button
            onClick={submit}
            disabled={disabled || submitting || filled === 0}
            className="btn-navy px-5 py-2 rounded-lg text-sm shadow-sm disabled:opacity-40">
            {submitting ? "재분석 중…" : "답변 반영 후 재분석"}
          </button>
        </div>
      )}
    </div>
  );
}
