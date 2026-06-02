'use client';

import useSWR from 'swr';
import { fetcher, endpoints } from './api';
import type {
  LiveMetrics,
  AgentState,
  Alert,
  SessionLog,
  ProcessStatus,
  LogResponse,
  LlmInfo,
} from './types';

/**
 * Live network metrics — polls every 2 seconds.
 */
export function useLiveMetrics() {
  return useSWR<LiveMetrics>(endpoints.metrics, fetcher, {
    refreshInterval: 2000,
    dedupingInterval: 1000,
  });
}

/**
 * Agent reasoning state — polls every 1 second for "live thinking" feel.
 */
export function useAgentState() {
  return useSWR<AgentState>(endpoints.agentState, fetcher, {
    refreshInterval: 1000,
    dedupingInterval: 500,
  });
}

/**
 * Anomaly alerts — polls every 3 seconds.
 */
export function useAlerts() {
  return useSWR<Alert[]>(endpoints.alerts, fetcher, {
    refreshInterval: 3000,
    dedupingInterval: 2000,
  });
}

/**
 * Agent session log — polls every 5 seconds.
 */
export function useSessions() {
  return useSWR<SessionLog[]>(endpoints.sessions, fetcher, {
    refreshInterval: 5000,
    dedupingInterval: 3000,
  });
}

/**
 * Log tails — polls every 3 seconds, only when enabled (panel expanded).
 */
export function useLogTail(source: 'inference' | 'agent', enabled: boolean) {
  const url = source === 'inference' ? endpoints.logsInference : endpoints.logsAgent;
  return useSWR<LogResponse>(
    enabled ? url : null,
    fetcher,
    {
      refreshInterval: 3000,
      dedupingInterval: 2000,
    }
  );
}

/**
 * Process status — polls every 5 seconds.
 */
export function useProcessStatus() {
  return useSWR<ProcessStatus>(endpoints.status, fetcher, {
    refreshInterval: 5000,
    dedupingInterval: 3000,
  });
}

/**
 * LLM info — fetched once (no polling).
 */
export function useLlmInfo() {
  return useSWR<LlmInfo>(endpoints.llmInfo, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60000,
  });
}
