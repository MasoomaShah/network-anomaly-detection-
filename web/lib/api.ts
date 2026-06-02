// ── API fetcher and endpoint helpers ──

// In production NEXT_PUBLIC_API_URL is set to the deployed backend URL.
// Locally it falls back to http://localhost:8001.
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8001';

/**
 * Generic fetcher for SWR — throws on non-OK responses.
 */
export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * POST helper for control endpoints.
 */
export async function post<T = unknown>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Endpoint paths ──

export const endpoints = {
  metrics:       '/api/metrics',
  agentState:    '/api/agent-state',
  alerts:        '/api/alerts',
  sessions:      '/api/sessions',
  logsInference: '/api/logs/inference',
  logsAgent:     '/api/logs/agent',
  status:        '/api/status',
  llmInfo:       '/api/llm-info',
  start:         '/api/start',
  stop:          '/api/stop',
  demo:          (scenario: string) => `/api/demo/${scenario}`,
  reset:         '/api/reset',
} as const;
