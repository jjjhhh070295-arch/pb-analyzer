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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center gap-3">
        <Link href="/" className="text-gray-400 hover:text-gray-600 text-sm">← 목록</Link>
        <h1 className="text-xl font-bold text-gray-900">고객 등록</h1>
      </header>

      <main className="max-w-lg mx-auto px-6 py-10">
        <form onSubmit={submit} className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">고객명 *</label>
            <input required value={form.name} onChange={set("name")}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="홍길동" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">생년월일 *</label>
            <input required value={form.birth_date} onChange={set("birth_date")}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="YYYY-MM-DD" pattern="\d{4}-\d{2}-\d{2}" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">담당 PB *</label>
            <input required value={form.primary_pb} onChange={set("primary_pb")}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="박상우" />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button type="submit" disabled={saving}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? "등록 중…" : "등록"}
          </button>
        </form>
      </main>
    </div>
  );
}
