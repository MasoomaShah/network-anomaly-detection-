'use client';

import { useState, useEffect } from 'react';
import { useAgentState, useProcessStatus } from '@/lib/hooks';
import type { AgentStatus } from '@/lib/types';

const STATUS_LABELS: Record<AgentStatus, string> = {
  idle:          'all clear',
  investigating: 'investigating',
  acting:        'acting',
  resolved:      'resolved',
  error:         'error',
};

const STATUS_COLORS: Record<AgentStatus, string> = {
  idle:          'var(--healthy)',
  investigating: 'var(--investigating)',
  acting:        'var(--accent)',
  resolved:      'var(--healthy)',
  error:         'var(--critical)',
};

export default function TopBar() {
  const { data: agentState } = useAgentState();
  const { data: processStatus } = useProcessStatus();
  const [clock, setClock] = useState('');

  useEffect(() => {
    function update() {
      setClock(new Date().toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }));
    }
    update();
    const id = setInterval(update, 10000);
    return () => clearInterval(id);
  }, []);

  const status: AgentStatus = agentState?.status || 'idle';
  const isMonitoring = processStatus?.overall === 'running';

  return (
    <div className="top-bar">
      <h1 className="top-bar-title">Network Troubleshooter</h1>
      <div className="top-bar-right">
        <div className="top-bar-status">
          <span
            className="status-dot"
            style={{ backgroundColor: STATUS_COLORS[status] }}
          />
          <span>
            {isMonitoring ? 'Monitoring' : 'Offline'}
            {' · '}
            {STATUS_LABELS[status]}
          </span>
        </div>
        <span className="top-bar-clock">{clock}</span>
      </div>
    </div>
  );
}
