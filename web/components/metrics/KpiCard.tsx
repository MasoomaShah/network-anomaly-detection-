'use client';

import Sparkline from './Sparkline';
import {
  METRIC_THRESHOLDS,
  METRIC_CONFIG,
  type MetricKey,
  type MetricThreshold,
} from '@/lib/types';

interface KpiCardProps {
  metricKey: MetricKey;
  value: number | null;
  history: number[];
}

function getStatusColorClass(value: number, threshold: MetricThreshold): string {
  const { green, yellow, dir } = threshold;
  if (dir === 'higher') {
    if (value >= green) return 'text-healthy';
    if (value >= yellow) return 'text-warning';
    return 'text-critical';
  } else {
    if (value <= green) return 'text-healthy';
    if (value <= yellow) return 'text-warning';
    return 'text-critical';
  }
}

// Map status class → a subtle sparkline stroke color
const SPARKLINE_COLORS: Record<string, string> = {
  'text-healthy':  'rgba(4, 215, 147, 0.55)',   // Caribbean Green dim
  'text-warning':  'rgba(255, 179, 0,   0.55)',  // amber dim
  'text-critical': 'rgba(255, 68,  68,  0.55)',  // coral dim
  'text-muted':    'rgba(255, 255, 255, 0.18)',   // white dim when no data
};

export default function KpiCard({ metricKey, value, history }: KpiCardProps) {
  const config = METRIC_CONFIG[metricKey];
  const threshold = METRIC_THRESHOLDS[metricKey];

  const hasValue = value !== null && value !== undefined && Number.isFinite(value);

  const colorClass = hasValue
    ? getStatusColorClass(value, threshold)
    : 'text-muted';

  const displayValue = hasValue
    ? (typeof value === 'number' && !Number.isInteger(value)
        ? value.toFixed(1)
        : String(value))
    : '—';

  return (
    <div className="glass-card kpi-card">
      <div className="kpi-label">{config.label}</div>
      <div className="kpi-value-row">
        <span className={`kpi-value ${colorClass}`}>
          {displayValue}
        </span>
        {hasValue && config.unit && <span className="kpi-unit">{config.unit}</span>}
      </div>
      <div className="kpi-sparkline">
        <Sparkline data={history} stroke={SPARKLINE_COLORS[colorClass] ?? 'rgba(255,255,255,0.20)'} />
      </div>
    </div>
  );
}
