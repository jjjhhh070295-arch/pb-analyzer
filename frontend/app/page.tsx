"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Customer, type Session } from "@/lib/api";

export default function Home() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.customers.list(), api.sessions.list()])
      .then(([c, s]) => { setCustomers(c); setSessions(s); })
      .finally(() => setLoading(false));
  }, []);

  const filtered = customers.filter(c =>
    c.name.includes(search) || c.customer_id.includes(search)
  );

  const latestSession = (customerId: string) =>
    sessions
      .filter(s => s.customer_id === customerId)
      .sort((a, b) => b.consult_datetime.localeCompare(a.consult_datetime))[0];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">PB 고객 분석 시스템</h1>
        <Link href="/customers/new" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
          + 고객 등록
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-6">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="고객명 또는 ID로 검색…"
            className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        {loading ? (
          <p className="text-gray-400 text-center py-12">불러오는 중…</p>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-4xl mb-3">👤</p>
            <p>등록된 고객이 없습니다.</p>
            <Link href="/customers/new" className="mt-4 inline-block text-blue-600 text-sm">고객 등록하기 →</Link>
          </div>
        ) : (
          <ul className="space-y-2">
            {filtered.map(c => {
              const latest = latestSession(c.customer_id);
              const confirmed = latest?.status === "확정";
              return (
                <li key={c.customer_id} className="bg-white border border-gray-200 rounded-xl px-5 py-4 flex items-center justify-between hover:shadow-sm transition-shadow">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-800">{c.name}</span>
                      <span className="text-xs text-gray-400 font-mono">{c.customer_id}</span>
                      {latest && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${confirmed ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                          {latest.status}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {c.birth_date} · 담당 {c.primary_pb}
                      {latest && <span className="ml-2">· 최근 상담 {latest.consult_date}</span>}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <Link href={`/sessions/new?customer_id=${c.customer_id}&pb_name=${encodeURIComponent(c.primary_pb)}`}
                      className="text-sm text-blue-600 hover:underline">새 상담</Link>
                    {latest && (
                      <Link href={`/sessions/${latest.session_id}`}
                        className="text-sm text-gray-500 hover:underline">결과 보기</Link>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}
