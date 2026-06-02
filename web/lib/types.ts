// ── TypeScript types matching the JSON schemas produced by the Python pipeline ──

// LIVE_METRICS_PATH
export interface MetricsData {
  latency_ms: number;
  packet_loss_pct: number;
  download_mbps: number;
  upload_mbps: number;
  connected_devices: number;
  dns_response_ms: number;
  gateway_ping_ms: number;
  jitter_ms: number;
}

export interface LiveMetrics {
  timestamp: string; // ISO
  metrics: MetricsData;
}

// AGENT_STATE_PATH
export type AgentStatus = 'idle' | 'investigating' | 'acting' | 'resolved' | 'error';
export type StepType = 'thought' | 'action' | 'observation' | 'fix' | 'error' | 'final';

export interface AgentStep {
  type: StepType;
  content: string;
  tool?: string;
  tool_input?: string;
  timestamp?: string;
}

export interface AgentState {
  status: AgentStatus;
  alert_id?: number;
  updated_at?: string;
  steps: AgentStep[];
  final_answer?: string;
}

// ALERTS_PATH (array)
export type Severity = 'low' | 'medium' | 'high';
export type AlertStatus = 'pending' | 'investigating' | 'resolved' | 'error';

export interface Alert {
  id: number;
  anomaly_type: string;
  severity: Severity;
  status: AlertStatus;
  timestamp: string; // ISO
  metrics?: Record<string, number>;
}

// AGENT_LOG_PATH (array)
export type SessionOutcome = 'resolved' | 'error' | 'escalated';

export interface SessionLog {
  session_id: number;
  anomaly_type: string;
  outcome: SessionOutcome;
  steps: unknown[];
  timestamp: string;
  alert_id?: number;
  severity?: string;
  final_answer?: string;
}

// Process status
export interface ProcessStatus {
  inference: 'running' | 'stopped';
  agent: 'running' | 'stopped';
  overall: 'running' | 'stopped';
}

// Log response
export interface LogResponse {
  lines: string[];
}

// LLM info
export interface LlmInfo {
  name: string;
}

// ── Metric thresholds for KPI color coding ──

export type ThresholdDirection = 'lower' | 'higher';

export interface MetricThreshold {
  green: number;
  yellow: number;
  dir: ThresholdDirection;
}

export const METRIC_THRESHOLDS: Record<keyof MetricsData, MetricThreshold> = {
  latency_ms:        { green: 50,  yellow: 200,  dir: 'lower'  },
  packet_loss_pct:   { green: 1,   yellow: 10,   dir: 'lower'  },
  download_mbps:     { green: 10,  yellow: 1,    dir: 'higher' },
  upload_mbps:       { green: 5,   yellow: 1,    dir: 'higher' },
  connected_devices: { green: 10,  yellow: 15,   dir: 'lower'  },
  dns_response_ms:   { green: 100, yellow: 1000, dir: 'lower'  },
  gateway_ping_ms:   { green: 20,  yellow: 100,  dir: 'lower'  },
  jitter_ms:         { green: 20,  yellow: 80,   dir: 'lower'  },
};

// Metric display labels and units
export const METRIC_CONFIG: Record<keyof MetricsData, { label: string; unit: string }> = {
  latency_ms:        { label: 'Latency',  unit: 'ms'   },
  packet_loss_pct:   { label: 'Pkt Loss', unit: '%'    },
  download_mbps:     { label: 'Download', unit: 'Mbps' },
  upload_mbps:       { label: 'Upload',   unit: 'Mbps' },
  connected_devices: { label: 'Devices',  unit: ''     },
  dns_response_ms:   { label: 'DNS',      unit: 'ms'   },
  gateway_ping_ms:   { label: 'Gateway',  unit: 'ms'   },
  jitter_ms:         { label: 'Jitter',   unit: 'ms'   },
};

// Metric key type for iteration
export type MetricKey = keyof MetricsData;
export const METRIC_KEYS: MetricKey[] = [
  'latency_ms',
  'packet_loss_pct',
  'download_mbps',
  'upload_mbps',
  'connected_devices',
  'dns_response_ms',
  'gateway_ping_ms',
  'jitter_ms',
];

// Demo scenarios
export const DEMO_SCENARIOS = [
  { key: 'bandwidth_flood', label: 'Bandwidth Flood' },
  { key: 'unknown_device',  label: 'Unknown Device'  },
  { key: 'dns_failure',     label: 'DNS Failure'     },
  { key: 'packet_loss',     label: 'Packet Loss'     },
] as const;

export type DemoScenario = typeof DEMO_SCENARIOS[number]['key'];
