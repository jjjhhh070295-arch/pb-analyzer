const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

// ─── 타입 ───────────────────────────────────────────────────────────────────

export interface Customer {
  customer_id: string;
  name: string;
  birth_date: string;
  primary_pb: string;
  registered_at: string;
}

export interface SearchResult {
  kind: "none" | "single" | "multiple";
  candidates: Customer[];
}

export type Severity = "red" | "yellow" | "gray";

export interface Flag {
  rule_id: string;
  severity: Severity;
  message: string;
  inline_factor: string | null;
  resolved: boolean;
}

export interface FactorMeta {
  status: "explicit" | "inferred" | "missing";
  evidence: string | null;
  confidence: "상" | "중" | "하" | null;
}

export interface AnalysisResult {
  goal_return: { meta: FactorMeta; return_min: number | null; return_max: number | null; raw_text: string | null };
  risk_tolerance: {
    status: string;
    willingness: { level: string | null; evidence: string | null; confidence: string | null };
    capacity: { level: string | null; evidence: string | null; confidence: string | null };
    binding: string | null;
  };
  horizon: { meta: FactorMeta; years: number | null };
  tax: { meta: FactorMeta; items: string[]; annual_financial_income: number | null };
  liquidity: { meta: FactorMeta; events: { when: string | null; amount: number | null; purpose: string | null }[] };
  legal: { meta: FactorMeta; items: string[] };
  unique: { meta: FactorMeta; notes: string[]; excluded_sectors: string[] };
  follow_up_questions: string[];
  optimizer_constraints: Record<string, unknown>;
  flags: Flag[];
  total_investable: number | null;
}

export interface Session {
  session_id: string;
  customer_id: string;
  customer_name: string;
  pb_name: string;
  consult_date: string;
  consult_datetime: string;
  status: string;
  raw_text: string;
  result: AnalysisResult;
  summary: Record<string, unknown>;
}

export interface PortfolioWeight {
  asset_id: string;
  name: string;
  category: string;
  weight: number;
  weight_pct: number;
}

export interface PortfolioMetrics {
  expected_return: number;
  expected_return_pct: number;
  downside_volatility: number;
  downside_volatility_pct: number;
  downside_risk_score: number;   // 0~100
  sortino_ratio: number;
  beta: number;
}

export interface PortfolioResult {
  weights: PortfolioWeight[];
  metrics: PortfolioMetrics;
  provisional: boolean;
  warnings: string[];
}

// ─── 고객 API ────────────────────────────────────────────────────────────────

export const api = {
  customers: {
    list: () => req<Customer[]>("/customers"),
    get: (id: string) => req<Customer>(`/customers/${id}`),
    search: (name: string) => req<SearchResult>(`/customers/search?name=${encodeURIComponent(name)}`),
    create: (body: { name: string; birth_date: string; primary_pb: string }) =>
      req<Customer>("/customers", { method: "POST", body: JSON.stringify(body) }),
  },
  portfolio: {
    optimize: (session_id: string, years = 3) =>
      req<PortfolioResult>("/portfolio/optimize", {
        method: "POST",
        body: JSON.stringify({ session_id, years }),
      }),
    universe: () => req<{ asset_id: string; ticker: string; name: string; category: string }[]>("/portfolio/universe"),
  },
  sessions: {
    list: (params?: { customer_id?: string; status?: string }) => {
      const qs = new URLSearchParams();
      if (params?.customer_id) qs.set("customer_id", params.customer_id);
      if (params?.status) qs.set("status", params.status);
      return req<Session[]>(`/sessions${qs.size ? "?" + qs : ""}`);
    },
    get: (id: string) => req<Session | { session_id: string; status: string }>(`/sessions/${id}`),
    getStatus: (id: string) => req<{ session_id: string; status: string; error?: string }>(`/sessions/${id}/status`),
    start: (body: { customer_id: string; pb_name: string; raw_text: string; consult_date?: string }) =>
      req<{ session_id: string; status: string }>("/sessions", { method: "POST", body: JSON.stringify(body) }),
    confirm: (id: string) => req<{ session_id: string; status: string }>(`/sessions/${id}/confirm`, { method: "PATCH" }),
    resolveFlag: (id: string, ruleId: string) =>
      req<{ resolved: boolean }>(`/sessions/${id}/flags/${ruleId}/resolve`, { method: "PATCH" }),
  },
};
