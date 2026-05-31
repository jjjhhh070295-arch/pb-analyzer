"use client";
import { useState } from "react";
import type { AnalysisResult } from "@/lib/api";

interface Props {
  result: AnalysisResult;
  onClose: () => void;
  onSave: (next: AnalysisResult) => Promise<void> | void;
}

const STATUS_OPTIONS = ["explicit", "inferred", "missing"] as const;
const CONF_OPTIONS = ["상", "중", "하"] as const;
const RISK_LEVELS = ["높음", "중립", "낮음"] as const;

export default function EditFactorsModal({ result, onClose, onSave }: Props) {
  const [r, setR] = useState<AnalysisResult>(JSON.parse(JSON.stringify(result)));
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState<"basic" | "tax" | "liquidity" | "legal_unique">("basic");

  // 백분율 ↔ 소수 변환 헬퍼
  const toPct = (n: number | null): string => n == null ? "" : String(Math.round(n * 1000) / 10);
  const fromPct = (s: string): number | null => {
    const t = s.trim();
    if (!t) return null;
    const v = parseFloat(t);
    return isNaN(v) ? null : v / 100;
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave(r);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
        <header className="bg-header-gradient text-white px-6 py-4 rounded-t-xl flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold">7요인 직접 수정</h2>
            <p className="text-blue-100 text-xs mt-0.5">PB 판단으로 결과를 수정합니다. 저장 시 검수중 상태로 돌아갑니다.</p>
          </div>
          <button onClick={onClose} className="text-blue-100 hover:text-gold text-xl leading-none">×</button>
        </header>

        <div className="border-b border-slate-200 px-4 pt-2 flex gap-1 overflow-x-auto">
          {([
            ["basic", "목표·위험·기간"],
            ["tax", "세금"],
            ["liquidity", "유동성"],
            ["legal_unique", "법적·고유"],
          ] as const).map(([key, label]) => (
            <button key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${tab === key ? "border-gold text-navy" : "border-transparent text-slate-500 hover:text-slate-700"}`}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {tab === "basic" && (
            <>
              {/* 목표수익률 */}
              <Section title="목표수익률">
                <div className="grid grid-cols-3 gap-3">
                  <Field label="하한 (%)">
                    <input type="number" step="0.1"
                      value={toPct(r.goal_return.return_min)}
                      onChange={e => setR({ ...r, goal_return: { ...r.goal_return, return_min: fromPct(e.target.value) }})}
                      className={inputCls} />
                  </Field>
                  <Field label="상한 (%)">
                    <input type="number" step="0.1"
                      value={toPct(r.goal_return.return_max)}
                      onChange={e => setR({ ...r, goal_return: { ...r.goal_return, return_max: fromPct(e.target.value) }})}
                      className={inputCls} />
                  </Field>
                  <Field label="원문 표현">
                    <input type="text"
                      value={r.goal_return.raw_text ?? ""}
                      onChange={e => setR({ ...r, goal_return: { ...r.goal_return, raw_text: e.target.value || null }})}
                      className={inputCls} placeholder="연 7~9%" />
                  </Field>
                </div>
                <MetaEditor
                  meta={r.goal_return.meta}
                  onChange={meta => setR({ ...r, goal_return: { ...r.goal_return, meta }})}
                />
              </Section>

              {/* 위험허용도 */}
              <Section title="위험허용도">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="의향 (willingness)">
                    <select value={r.risk_tolerance.willingness.level ?? ""}
                      onChange={e => setR({ ...r, risk_tolerance: { ...r.risk_tolerance, willingness: { ...r.risk_tolerance.willingness, level: e.target.value || null }}})}
                      className={inputCls}>
                      <option value="">미정</option>
                      {RISK_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </Field>
                  <Field label="능력 (capacity)">
                    <select value={r.risk_tolerance.capacity.level ?? ""}
                      onChange={e => setR({ ...r, risk_tolerance: { ...r.risk_tolerance, capacity: { ...r.risk_tolerance.capacity, level: e.target.value || null }}})}
                      className={inputCls}>
                      <option value="">미정</option>
                      {RISK_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </Field>
                </div>
                <Field label="Binding 축 (적용할 보수적인 쪽)">
                  <select value={r.risk_tolerance.binding ?? ""}
                    onChange={e => setR({ ...r, risk_tolerance: { ...r.risk_tolerance, binding: e.target.value || null }})}
                    className={inputCls}>
                    <option value="">미정</option>
                    <option value="willingness">의향 (willingness)</option>
                    <option value="capacity">능력 (capacity)</option>
                  </select>
                </Field>
              </Section>

              {/* 투자 기간 */}
              <Section title="투자 기간">
                <Field label="기간 (년)">
                  <input type="number" step="0.5"
                    value={r.horizon.years ?? ""}
                    onChange={e => setR({ ...r, horizon: { ...r.horizon, years: e.target.value ? parseFloat(e.target.value) : null }})}
                    className={inputCls} />
                </Field>
                <MetaEditor
                  meta={r.horizon.meta}
                  onChange={meta => setR({ ...r, horizon: { ...r.horizon, meta }})}
                />
              </Section>
            </>
          )}

          {tab === "tax" && (
            <Section title="세금 요인">
              <Field label="연간 금융소득 (원, 빈 칸이면 미상)">
                <input type="number"
                  value={r.tax.annual_financial_income ?? ""}
                  onChange={e => setR({ ...r, tax: { ...r.tax, annual_financial_income: e.target.value ? parseInt(e.target.value, 10) : null }})}
                  className={inputCls} placeholder="예: 30000000" />
              </Field>
              <ListEditor
                label="세무 항목"
                items={r.tax.items}
                onChange={items => setR({ ...r, tax: { ...r.tax, items }})}
                placeholder="예: 배당소득 있음"
              />
              <MetaEditor meta={r.tax.meta} onChange={meta => setR({ ...r, tax: { ...r.tax, meta }})} />
            </Section>
          )}

          {tab === "liquidity" && (
            <Section title="유동성 필요시기">
              <div className="space-y-3">
                {r.liquidity.events.map((e, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 items-start">
                    <input className={inputCls + " col-span-3"} placeholder="시점 (예: 1년 내)"
                      value={e.when ?? ""}
                      onChange={ev => {
                        const events = [...r.liquidity.events];
                        events[i] = { ...e, when: ev.target.value || null };
                        setR({ ...r, liquidity: { ...r.liquidity, events }});
                      }} />
                    <input className={inputCls + " col-span-4"} type="number" placeholder="금액 (원)"
                      value={e.amount ?? ""}
                      onChange={ev => {
                        const events = [...r.liquidity.events];
                        events[i] = { ...e, amount: ev.target.value ? parseInt(ev.target.value, 10) : null };
                        setR({ ...r, liquidity: { ...r.liquidity, events }});
                      }} />
                    <input className={inputCls + " col-span-4"} placeholder="용도"
                      value={e.purpose ?? ""}
                      onChange={ev => {
                        const events = [...r.liquidity.events];
                        events[i] = { ...e, purpose: ev.target.value || null };
                        setR({ ...r, liquidity: { ...r.liquidity, events }});
                      }} />
                    <button onClick={() => {
                      const events = r.liquidity.events.filter((_, idx) => idx !== i);
                      setR({ ...r, liquidity: { ...r.liquidity, events }});
                    }}
                      className="col-span-1 text-slate-400 hover:text-red-500 py-2">×</button>
                  </div>
                ))}
                <button onClick={() => setR({ ...r, liquidity: { ...r.liquidity, events: [...r.liquidity.events, { when: null, amount: null, purpose: null }]}})}
                  className="text-xs text-navy hover:underline font-medium">+ 이벤트 추가</button>
              </div>
              <MetaEditor meta={r.liquidity.meta} onChange={meta => setR({ ...r, liquidity: { ...r.liquidity, meta }})} />
            </Section>
          )}

          {tab === "legal_unique" && (
            <>
              <Section title="법적 제약">
                <ListEditor
                  label="법적 항목"
                  items={r.legal.items}
                  onChange={items => setR({ ...r, legal: { ...r.legal, items }})}
                  placeholder="예: 신탁 진행 중"
                />
                <MetaEditor meta={r.legal.meta} onChange={meta => setR({ ...r, legal: { ...r.legal, meta }})} />
              </Section>

              <Section title="고유 상황">
                <ListEditor
                  label="메모"
                  items={r.unique.notes}
                  onChange={notes => setR({ ...r, unique: { ...r.unique, notes }})}
                  placeholder="예: ESG 선호"
                />
                <ListEditor
                  label="배제 업종"
                  items={r.unique.excluded_sectors}
                  onChange={excluded_sectors => setR({ ...r, unique: { ...r.unique, excluded_sectors }})}
                  placeholder="예: tobacco"
                />
                <MetaEditor meta={r.unique.meta} onChange={meta => setR({ ...r, unique: { ...r.unique, meta }})} />
              </Section>
            </>
          )}
        </div>

        <footer className="border-t border-slate-200 px-6 py-4 flex justify-end gap-2 bg-slate-50 rounded-b-xl">
          <button onClick={onClose} disabled={saving}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">취소</button>
          <button onClick={save} disabled={saving}
            className="btn-navy px-5 py-2 rounded-lg text-sm shadow-sm">
            {saving ? "저장 중…" : "저장"}
          </button>
        </footer>
      </div>
    </div>
  );
}

const inputCls = "border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 bg-white w-full";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card-premium p-5">
      <p className="text-sm font-semibold text-navy mb-3 flex items-center gap-2">
        <span className="w-1 h-4 bg-gold rounded-sm" />
        {title}
      </p>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-slate-500 mb-1 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

function MetaEditor({ meta, onChange }: { meta: { status: string; evidence: string | null; confidence: string | null }; onChange: (m: { status: "explicit" | "inferred" | "missing"; evidence: string | null; confidence: "상" | "중" | "하" | null }) => void }) {
  return (
    <div className="grid grid-cols-3 gap-3 pt-2 border-t border-slate-100">
      <Field label="상태">
        <select value={meta.status} onChange={e => onChange({ ...meta, status: e.target.value as "explicit" | "inferred" | "missing", evidence: meta.evidence, confidence: (meta.confidence as "상" | "중" | "하" | null) })} className={inputCls}>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </Field>
      <Field label="신뢰도">
        <select value={meta.confidence ?? ""} onChange={e => onChange({ ...meta, status: meta.status as "explicit" | "inferred" | "missing", confidence: (e.target.value || null) as "상" | "중" | "하" | null })} className={inputCls}>
          <option value="">미정</option>
          {CONF_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </Field>
      <Field label="근거">
        <input type="text" value={meta.evidence ?? ""} onChange={e => onChange({ ...meta, status: meta.status as "explicit" | "inferred" | "missing", confidence: (meta.confidence as "상" | "중" | "하" | null), evidence: e.target.value || null })} className={inputCls} />
      </Field>
    </div>
  );
}

function ListEditor({ label, items, onChange, placeholder }: { label: string; items: string[]; onChange: (items: string[]) => void; placeholder?: string }) {
  return (
    <Field label={label}>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex gap-2">
            <input type="text" value={item}
              onChange={e => { const next = [...items]; next[i] = e.target.value; onChange(next); }}
              className={inputCls} placeholder={placeholder} />
            <button onClick={() => onChange(items.filter((_, idx) => idx !== i))}
              className="text-slate-400 hover:text-red-500 px-2">×</button>
          </div>
        ))}
        <button onClick={() => onChange([...items, ""])}
          className="text-xs text-navy hover:underline font-medium">+ 항목 추가</button>
      </div>
    </Field>
  );
}
