interface Props { questions: string[] }

export default function FollowUpPanel({ questions }: Props) {
  if (questions.length === 0) return null;
  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
      <p className="text-sm font-semibold text-blue-700 mb-2">추가 확인 질문 ({questions.length})</p>
      <ol className="space-y-1.5">
        {questions.map((q, i) => (
          <li key={i} className="text-sm text-blue-800 flex gap-2">
            <span className="font-mono text-xs text-blue-400 mt-0.5">{i + 1}.</span>
            {q}
          </li>
        ))}
      </ol>
    </div>
  );
}
