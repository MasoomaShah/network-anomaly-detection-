'use client';

import { useState, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import Sidebar from '@/components/layout/Sidebar';
import TopBar from '@/components/layout/TopBar';
import KpiCard from '@/components/metrics/KpiCard';
import ReasoningPanel from '@/components/agent/ReasoningPanel';
import AnomalyFeed from '@/components/feed/AnomalyFeed';
import ActionLog from '@/components/feed/ActionLog';
import LogTabs from '@/components/streams/LogTabs';
import { useLiveMetrics } from '@/lib/hooks';
import { METRIC_KEYS, type MetricKey } from '@/lib/types';

// Dynamic import for the 3D globe (SSR disabled — needs browser APIs)
const NetworkGlobe = dynamic(
  () => import('@/components/three/NetworkGlobe'),
  { ssr: false }
);

// Rolling history window for sparklines (last 30 readings ≈ 60 seconds at 2s poll)
const HISTORY_SIZE = 30;

export default function DashboardPage() {
  const { data: liveMetrics } = useLiveMetrics();
  const [history, setHistory] = useState<Record<MetricKey, number[]>>(() => {
    const h: Record<string, number[]> = {};
    for (const key of METRIC_KEYS) {
      h[key] = [];
    }
    return h as Record<MetricKey, number[]>;
  });

  // Track the last timestamp to avoid duplicate pushes
  const lastTs = useRef<string>('');

  useEffect(() => {
    if (!liveMetrics?.metrics || !liveMetrics?.timestamp) return;
    if (liveMetrics.timestamp === lastTs.current) return;
    lastTs.current = liveMetrics.timestamp;

    setHistory(prev => {
      const next = { ...prev };
      for (const key of METRIC_KEYS) {
        const val = liveMetrics.metrics[key] ?? 0;
        const arr = [...prev[key], val];
        next[key] = arr.length > HISTORY_SIZE ? arr.slice(-HISTORY_SIZE) : arr;
      }
      return next;
    });
  }, [liveMetrics]);

  const metrics = liveMetrics?.metrics;

  return (
    <>
      {/* 3D Background — fixed, z-index: 0 */}
      <NetworkGlobe />
      <div className="globe-vignette" />

      {/* App Shell — z-index: 10 */}
      <div className="app-shell">
        <Sidebar />

        <main className="main-content">
          <TopBar />

          <div className="main-body">
            {/* KPI Cards */}
            <div>
              <div className="section-label">Live Metrics</div>
              <div className="kpi-grid">
                {METRIC_KEYS.map(key => (
                  <KpiCard
                    key={key}
                    metricKey={key}
                    value={metrics ? (metrics[key] ?? null) : null}
                    history={history[key]}
                  />
                ))}
              </div>
            </div>

            {/* Two-Column: Agent Reasoning + Anomaly Feed */}
            <div className="two-col">
              <div>
                <ReasoningPanel />
              </div>
              <div>
                <AnomalyFeed />
                <ActionLog />
              </div>
            </div>

            {/* Log Streams */}
            <LogTabs />
          </div>
        </main>
      </div>
    </>
  );
}
