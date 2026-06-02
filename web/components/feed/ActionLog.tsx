'use client';

import { useSessions } from '@/lib/hooks';
import type { SessionLog, SessionOutcome } from '@/lib/types';

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '';
  }
}

function formatType(anomalyType: string): string {
  return anomalyType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

const outcomeColor: Record<SessionOutcome, string> = {
  resolved:  'var(--healthy)',
  error:     'var(--critical)',
  escalated: 'var(--warning)',
};

export default function ActionLog() {
  const { data: sessions } = useSessions();

  const sortedSessions = sessions
    ? [...sessions].reverse().slice(0, 10)
    : [];

  return (
    <div className="action-log-section">
      <div className="section-label">Action Log</div>

      {sortedSessions.length === 0 ? (
        <div className="empty-state small">
          <div className="empty-text">No actions taken yet.</div>
        </div>
      ) : (
        <div className="feed-scroll">
          {sortedSessions.map((entry: SessionLog) => (
            <div key={entry.session_id} className="feed-row">
              <span className="feed-id">S{String(entry.session_id).padStart(2, '0')}</span>
              <span className="feed-time">{formatTime(entry.timestamp)}</span>
              <span className="feed-type">{formatType(entry.anomaly_type)}</span>
              <span className="feed-steps">{entry.steps.length} steps</span>
              <span
                className="status-pill"
                style={{
                  borderColor: outcomeColor[entry.outcome],
                  color: outcomeColor[entry.outcome],
                }}
              >
                {entry.outcome}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
