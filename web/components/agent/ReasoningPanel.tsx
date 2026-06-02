'use client';

import { useAgentState } from '@/lib/hooks';
import StepCard from './StepCard';
import DiagnosisReport from './DiagnosisReport';
import { Brain } from 'lucide-react';

export default function ReasoningPanel() {
  const { data: agentState } = useAgentState();

  const status = agentState?.status || 'idle';
  const steps = agentState?.steps || [];
  const finalAnswer = agentState?.final_answer;
  const isError = status === 'error';

  const statusLabel = {
    idle: 'idle',
    investigating: 'investigating',
    acting: 'acting',
    resolved: 'resolved',
    error: 'error',
  }[status] || status;

  return (
    <div className="glass-card panel-card panel-focal">
      <div className="section-label">Agent Reasoning</div>

      {status !== 'idle' && (
        <div className="agent-status-line">
          <span
            className="agent-status-dot"
            style={{
              backgroundColor:
                status === 'investigating' || status === 'acting'
                  ? 'var(--accent)'
                  : status === 'resolved'
                    ? 'var(--healthy)'
                    : status === 'error'
                      ? 'var(--critical)'
                      : 'var(--text-muted)',
            }}
          />
          <span className="agent-status-text">{statusLabel}</span>
        </div>
      )}

      {steps.length === 0 && !finalAnswer ? (
        <div className="empty-state">
          <Brain size={28} strokeWidth={1.25} className="empty-icon" />
          <div className="empty-text">
            Agent is idle. Anomalies will surface here as the LSTM detects them.
          </div>
        </div>
      ) : (
        <div className="steps-scroll">
          {steps.map((step, i) => (
            <StepCard key={i} step={step} />
          ))}
        </div>
      )}

      {finalAnswer && (
        <DiagnosisReport content={finalAnswer} isError={isError} />
      )}
    </div>
  );
}
