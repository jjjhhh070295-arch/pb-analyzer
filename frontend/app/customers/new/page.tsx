"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function NewCustomer() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", birth_date: "", primary_pb: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.customers.create(form);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록 실패");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-header-gradient text-white">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center gap-3">
          <Link href="/" className="text-blue-100 hover:text-gold text-xs font-medium">← 목록</Link>
          <span className="text-blue-200">|</span>
          <h1 className="text-lg font-bold tracking-tight">신규 고객 등록</h1>
        </div>
        <div className="gold-accent-line" />
      </header>

      <main className="max-w-lg mx-auto px-6 py-12">
        <form onSubmit={submit} className="card-premium p-7 space-y-6">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wider">고객명</label>
            <input required value={form.name} onChange={set("name")}
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 bg-white"
              placeholder="홍길동" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wider">생년월일</label>
            <input required value={form.birth_date} onChange={set("birth_date")}
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 bg-white"
              placeholder="YYYY-MM-DD" pattern="\d{4}-\d{2}-\d{2}" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2 uppercase tracking-wider">담당 PB</label>
            <input required value={form.primary_pb} onChange={set("primary_pb")}
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-900/15 focus:border-blue-900 bg-white"
              placeholder="박상우" />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={saving}
            className="btn-navy w-full py-3 rounded-lg text-sm shadow-md">
            {saving ? "등록 중…" : "등록"}
          </button>
        </form>
      </main>
    </div>
  );
}
