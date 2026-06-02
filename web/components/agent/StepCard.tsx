'use client';

import type { AgentStep, StepType } from '@/lib/types';

const STEP_COLORS: Record<StepType, string> = {
  thought:     'var(--investigating)',
  action:      'var(--accent)',
  observation: 'var(--healthy)',
  fix:         'var(--accent)',
  error:       'var(--critical)',
  final:       'var(--accent)',
};

const STEP_LABELS: Record<StepType, string> = {
  thought:     'THOUGHT',
  action:      'ACTION',
  observation: 'OBSERVATION',
  fix:         'FIX',
  error:       'ERROR',
  final:       'FINAL',
};

interface StepCardProps {
  step: AgentStep;
}

function stripEmojis(text: string): string {
  if (!text) return '';
  // Removes common emojis like wrenches, crosses, checkmarks, and robots
  return text
    .replace(/[\u2600-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDF00-\uDFFF]|\uD83D[\uDC00-\uDDFF]|\uD83E[\uDD00-\uDFFF]/g, '')
    .trim();
}

export default function StepCard({ step }: StepCardProps) {
  const color = STEP_COLORS[step.type] || 'var(--text-secondary)';
  const label = STEP_LABELS[step.type] || step.type.toUpperCase();
  const cleanContent = step.content ? stripEmojis(step.content) : '';

  return (
    <div
      className="step-card"
      style={{ borderLeftColor: color }}
    >
      <div className="step-type" style={{ color }}>
        {label}
      </div>
      {step.tool && (
        <div className="step-tool">
          {step.tool}({step.tool_input || ''})
        </div>
      )}
      <div className="step-content">
        {cleanContent.slice(0, 600)}
      </div>
    </div>
  );
}
