'use client';

import { useAlerts } from '@/lib/hooks';
import type { Alert, Severity, AlertStatus } from '@/lib/types';

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return iso?.slice(0, 5) || '';
  }
}

function formatType(anomalyType: string): string {
  return anomalyType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

const severityColor: Record<Severity, string> = {
  high:   'var(--critical)',
  medium: 'var(--warning)',
  low:    'var(--healthy)',
};

const statusColor: Record<AlertStatus, string> = {
  pending:       'var(--info)',
  investigating: 'var(--investigating)',
  resolved:      'var(--healthy)',
  error:         'var(--critical)',
};

export default function AnomalyFeed() {
  const { data: alerts } = useAlerts();

  const sortedAlerts = alerts
    ? [...alerts].reverse().slice(0, 15)
    : [];

  return (
    <div className="glass-card panel-card">
      <div className="section-label">Anomaly Feed</div>

      {sortedAlerts.length === 0 ? (
        <div className="empty-state">
          <div className="empty-text">No anomalies detected yet.</div>
        </div>
      ) : (
        <div className="feed-scroll">
          {sortedAlerts.map((alert: Alert) => (
            <div key={alert.id} className="feed-row">
              <span className="feed-id">#{alert.id}</span>
              <span className="feed-time">{formatTime(alert.timestamp)}</span>
              <span
                className="status-pill"
                style={{ borderColor: severityColor[alert.severity], color: severityColor[alert.severity] }}
              >
                {alert.severity}
              </span>
              <span className="feed-type">{formatType(alert.anomaly_type)}</span>
              <span
                className="status-pill"
                style={{ borderColor: statusColor[alert.status], color: statusColor[alert.status] }}
              >
                {alert.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
