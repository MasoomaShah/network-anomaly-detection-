'use client';

import { useState } from 'react';
import { useLogTail } from '@/lib/hooks';
import { ChevronDown, ChevronRight } from 'lucide-react';

function colorizeLogLine(line: string): { text: string; color?: string } {
  if (line.startsWith('ANOMALY') || line.includes('→ ANOMALY')) {
    return { text: line, color: 'var(--critical)' };
  }
  if (line.startsWith('ERROR') || line.includes('ERROR')) {
    return { text: line, color: 'var(--critical)' };
  }
  if (line.startsWith('RESOLVED') || line.includes('RESOLVED')) {
    return { text: line, color: 'var(--healthy)' };
  }
  return { text: line };
}

export default function LogTabs() {
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<'inference' | 'agent'>('inference');

  const { data: inferenceData, isLoading: inferenceLoading } = useLogTail('inference', expanded);
  const { data: agentData,    isLoading: agentLoading    } = useLogTail('agent', expanded && activeTab === 'agent');

  const isLoading = activeTab === 'inference' ? inferenceLoading : agentLoading;
  const lines     = activeTab === 'inference'
    ? inferenceData?.lines || []
    : agentData?.lines     || [];

  return (
    <div className="log-panel">
      <button
        className="log-panel-header"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded
          ? <ChevronDown  size={16} strokeWidth={1.5} />
          : <ChevronRight size={16} strokeWidth={1.5} />
        }
        <span className="section-label" style={{ marginBottom: 0 }}>Streams</span>
      </button>

      {expanded && (
        <>
          <div className="log-tabs">
            <button
              className={`log-tab ${activeTab === 'inference' ? 'active' : ''}`}
              onClick={() => setActiveTab('inference')}
            >
              Inference
            </button>
            <button
              className={`log-tab ${activeTab === 'agent' ? 'active' : ''}`}
              onClick={() => setActiveTab('agent')}
            >
              Agent
            </button>
          </div>

          <div className="log-content">
            {/* Still fetching for the first time */}
            {isLoading && lines.length === 0 ? (
              <div className="log-empty">Connecting to log stream…</div>

            /* Fetch returned but log is genuinely empty */
            ) : !isLoading && lines.length === 0 ? (
              <div className="log-empty">
                {activeTab === 'inference'
                  ? 'No inference output yet — model loads in ~30 s after Start Monitoring.'
                  : 'No agent output yet. Trigger a demo scenario to see activity.'}
              </div>

            ) : (
              lines.map((line, i) => {
                const { text, color } = colorizeLogLine(line);
                return (
                  <div key={i} className="log-line" style={color ? { color } : undefined}>
                    {text}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}
