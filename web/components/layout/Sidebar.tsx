'use client';

import { useState } from 'react';
import { useProcessStatus, useLlmInfo } from '@/lib/hooks';
import { post, endpoints } from '@/lib/api';
import { DEMO_SCENARIOS } from '@/lib/types';
import {
  ShieldCheck,
  Activity,
  AlertTriangle,
  ScrollText,
  FileText,
  Play,
  Square,
  Zap,
  Wifi,
  Globe,
  TrendingDown,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Terminal,
} from 'lucide-react';

/* ── Manual trigger instructions per scenario ───────────────────────── */
interface CmdStep {
  label: string;
  cmd?: string;      // copyable command
  note?: string;     // plain-text annotation
}

const MANUAL_TRIGGERS: Record<string, { title: string; steps: CmdStep[] }> = {
  bandwidth_flood: {
    title: 'Real Bandwidth Saturation',
    steps: [
      {
        label: 'Download 10 GB file (PowerShell)',
        cmd: 'curl.exe -o NUL https://speed.hetzner.de/10GB.bin',
        note: 'Stop with Ctrl + C',
      },
      {
        label: 'Parallel downloads (floods harder)',
        cmd: '1..4 | ForEach-Object -Parallel { curl.exe -o NUL https://speed.hetzner.de/10GB.bin }',
        note: 'PowerShell 7+ required',
      },
    ],
  },
  packet_loss: {
    title: 'Real Packet Loss via Clumsy',
    steps: [
      {
        label: 'Download Clumsy (Windows)',
        note: 'https://jagt.me/clumsy/',
      },
      {
        label: 'Find your local IP (run first)',
        cmd: '(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress',
      },
      {
        label: 'Clumsy filter — paste into Filter field',
        cmd: 'outbound and ip.DstAddr == <YOUR_IP>',
        note: 'Replace <YOUR_IP> with result above',
      },
      {
        label: 'Clumsy Drop settings',
        note: 'Tab: Drop   ☑ Outbound   Chance: 70%',
      },
      {
        label: 'Click Start in Clumsy, then Stop to restore',
        note: 'Clumsy restores traffic on Stop',
      },
    ],
  },
  dns_failure: {
    title: 'Real DNS Failure',
    steps: [
      {
        label: '① Get your adapter name (run first)',
        cmd: 'Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -ExpandProperty Name',
        note: 'e.g. "Wi-Fi" or "Ethernet" — use the result in step ②',
      },
      {
        label: '② Point DNS at a non-existent server (Admin PS)',
        cmd: 'netsh interface ipv4 set dnsserver "Wi-Fi" static 192.168.254.254 primary',
        note: 'Replace "Wi-Fi" with your adapter name from step ①',
      },
      {
        label: '③ Stop DNS cache service so it takes effect immediately',
        cmd: 'net stop dnscache',
        note: 'This forces every lookup to hit the dead server',
      },
      {
        label: '④ Flush any remaining cache',
        cmd: 'ipconfig /flushdns',
      },
      {
        label: '— RESTORE when done (Admin PS) —',
        cmd: 'net start dnscache ; netsh interface ipv4 set dnsserver "Wi-Fi" dhcp ; ipconfig /flushdns',
        note: 'Replace "Wi-Fi" with your adapter name',
      },
    ],
  },
  unknown_device: {
    title: 'Real Unknown Device',
    steps: [
      {
        label: 'Connect any new device to your Wi-Fi',
        note: 'Phone hotspot, guest device, VM, etc.',
      },
      {
        label: 'Or add a static ARP entry (Admin)',
        cmd: 'arp -s 192.168.1.200 AA-BB-CC-DD-EE-FF',
        note: 'Simulates a new MAC on the subnet',
      },
      {
        label: 'Remove when done',
        cmd: 'arp -d 192.168.1.200',
      },
    ],
  },
};

/* ── Copy button ─────────────────────────────────────────────────────── */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <button
      onClick={handleCopy}
      title="Copy command"
      style={{
        flexShrink: 0,
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: copied ? 'var(--caribbean)' : 'var(--text-muted)',
        padding: '2px',
        display: 'flex',
        alignItems: 'center',
        transition: 'color 0.15s',
      }}
    >
      {copied
        ? <Check size={11} strokeWidth={2.5} />
        : <Copy size={11} strokeWidth={1.8} />
      }
    </button>
  );
}

/* ── Trigger panel ───────────────────────────────────────────────────── */
function TriggerPanel({ scenarioKey }: { scenarioKey: string }) {
  const trigger = MANUAL_TRIGGERS[scenarioKey];
  if (!trigger) return null;

  return (
    <div style={{
      margin: '4px 0 2px',
      padding: '10px 10px 8px',
      background: 'rgba(10, 78, 67, 0.30)',
      border: '1px solid rgba(4, 215, 147, 0.14)',
      borderRadius: '6px',
      display: 'flex',
      flexDirection: 'column',
      gap: '7px',
    }}>
      {/* Panel title */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '5px',
        color: 'var(--caribbean)',
        fontSize: '9px',
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        marginBottom: '1px',
      }}>
        <Terminal size={10} strokeWidth={2} />
        {trigger.title}
      </div>

      {trigger.steps.map((step, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {/* Step label */}
          <div style={{
            fontSize: '10px',
            color: 'var(--text-secondary)',
            fontWeight: 500,
          }}>
            {step.label}
          </div>

          {/* Copyable command */}
          {step.cmd && (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '4px',
              background: 'rgba(12, 19, 25, 0.70)',
              border: '1px solid rgba(6, 125, 93, 0.20)',
              borderRadius: '4px',
              padding: '5px 7px',
            }}>
              <code style={{
                flex: 1,
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-mono)',
                lineHeight: 1.45,
                wordBreak: 'break-all',
                whiteSpace: 'pre-wrap',
                userSelect: 'all',
              }}>
                {step.cmd}
              </code>
              <CopyButton text={step.cmd} />
            </div>
          )}

          {/* Plain-text note */}
          {step.note && (
            <div style={{
              fontSize: '10px',
              color: 'var(--text-muted)',
              fontStyle: 'italic',
              paddingLeft: '2px',
            }}>
              {step.note}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Scenario icons ──────────────────────────────────────────────────── */
const SCENARIO_ICONS: Record<string, React.ReactNode> = {
  bandwidth_flood: <Zap       size={14} strokeWidth={1.5} />,
  unknown_device:  <Wifi      size={14} strokeWidth={1.5} />,
  dns_failure:     <Globe     size={14} strokeWidth={1.5} />,
  packet_loss:     <TrendingDown size={14} strokeWidth={1.5} />,
};

/* ═══════════════════════════════════════════════════════════════════════
   Sidebar
   ═══════════════════════════════════════════════════════════════════════ */
export default function Sidebar() {
  const { data: status, mutate: mutateStatus } = useProcessStatus();
  const { data: llmInfo } = useLlmInfo();

  const [demoOpen,    setDemoOpen]    = useState(true);
  const [openTrigger, setOpenTrigger] = useState<string | null>(null);
  const [loading,     setLoading]     = useState<string | null>(null);
  const [error,       setError]       = useState<string | null>(null);

  const isRunning       = status?.overall   === 'running';
  const inferenceRunning = status?.inference === 'running';
  const agentRunning    = status?.agent     === 'running';

  async function handleStart() {
    setLoading('start'); setError(null);
    try { await post(endpoints.start); await mutateStatus(); }
    catch { setError('Failed to connect to backend server. Make sure FastAPI server is running on port 8001.'); }
    finally { setLoading(null); }
  }

  async function handleStop() {
    setLoading('stop'); setError(null);
    try { await post(endpoints.stop); await mutateStatus(); }
    catch { setError('Failed to connect to backend server. Make sure FastAPI server is running on port 8001.'); }
    finally { setLoading(null); }
  }

  async function handleDemo(scenario: string) {
    setLoading(scenario); setError(null);
    try {
      if (!isRunning) {
        await post(endpoints.start);
        await new Promise(r => setTimeout(r, 2000));
      }
      await post(endpoints.demo(scenario));
      await mutateStatus();
    } catch {
      setError('Failed to connect to backend server. Make sure FastAPI server is running on port 8001.');
    } finally { setLoading(null); }
  }

  async function handleReset() {
    setLoading('reset'); setError(null);
    try { await post(endpoints.reset); await mutateStatus(); }
    catch { setError('Failed to connect to backend server. Make sure FastAPI server is running on port 8001.'); }
    finally { setLoading(null); }
  }

  function toggleTrigger(key: string) {
    setOpenTrigger(prev => prev === key ? null : key);
  }

  return (
    <aside className="sidebar">

      {/* Brand */}
      <div className="sidebar-brand">
        <ShieldCheck size={18} strokeWidth={1.5} color="var(--accent)" />
        <span className="sidebar-brand-text">Network Troubleshooter</span>
      </div>

      {llmInfo?.name && (
        <div className="sidebar-llm-pill">{llmInfo.name}</div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          margin: '4px 4px 8px',
          padding: '10px 12px',
          background: 'rgba(255, 68, 68, 0.08)',
          border: '1px solid rgba(255, 68, 68, 0.28)',
          borderRadius: '6px',
          color: 'var(--critical)',
          fontSize: '11px',
          lineHeight: '1.4',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}>
          <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={12} />
            <span>Connection Error</span>
          </div>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{
            background: 'none', border: 'none',
            color: 'var(--text-secondary)', fontSize: '10px',
            textDecoration: 'underline', cursor: 'pointer',
            textAlign: 'left', padding: 0, marginTop: '4px',
          }}>Dismiss</button>
        </div>
      )}

      <div className="sidebar-divider" />

      {/* Nav */}
      <button className="nav-item active"><Activity size={16} strokeWidth={1.5} />Live</button>
      <button className="nav-item"><AlertTriangle size={16} strokeWidth={1.5} />Anomalies</button>
      <button className="nav-item"><ScrollText size={16} strokeWidth={1.5} />Sessions</button>
      <button className="nav-item"><FileText size={16} strokeWidth={1.5} />Logs</button>

      <div className="sidebar-divider" />

      {/* Monitoring */}
      <div className="sidebar-section-label">Monitoring</div>
      <div className="process-status-row">
        <span className={`status-dot ${inferenceRunning ? 'running' : 'stopped'}`} />
        <span>Inference</span>
      </div>
      <div className="process-status-row">
        <span className={`status-dot ${agentRunning ? 'running' : 'stopped'}`} />
        <span>Agent</span>
      </div>
      <div style={{ marginTop: 8 }}>
        {isRunning ? (
          <button className="ghost-button" onClick={handleStop} disabled={loading === 'stop'}>
            <Square size={14} strokeWidth={1.5} />
            {loading === 'stop' ? 'Stopping...' : 'Stop Monitoring'}
          </button>
        ) : (
          <button className="primary-button" onClick={handleStart} disabled={loading === 'start'}>
            <Play size={14} strokeWidth={1.5} />
            {loading === 'start' ? 'Starting...' : 'Start Monitoring'}
          </button>
        )}
      </div>

      <div className="sidebar-divider" />

      {/* Demo Scenarios */}
      <button className="nav-item" onClick={() => setDemoOpen(!demoOpen)} style={{ gap: 6 }}>
        {demoOpen
          ? <ChevronDown  size={14} strokeWidth={1.5} />
          : <ChevronRight size={14} strokeWidth={1.5} />
        }
        <span className="sidebar-section-label" style={{ margin: 0, padding: 0 }}>
          Demo Scenarios
        </span>
      </button>

      {demoOpen && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {DEMO_SCENARIOS.map(({ key, label }) => (
            <div key={key}>
              {/* Demo inject button + trigger toggle */}
              <div style={{ display: 'flex', gap: 4 }}>

                {/* Inject anomaly */}
                <button
                  className="demo-button"
                  onClick={() => handleDemo(key)}
                  disabled={loading === key}
                  style={{ flex: 1 }}
                >
                  {SCENARIO_ICONS[key]}
                  {loading === key ? 'Injecting...' : label}
                </button>

                {/* Toggle real-trigger panel */}
                <button
                  onClick={() => toggleTrigger(key)}
                  title="Show manual trigger commands"
                  style={{
                    flexShrink: 0,
                    width: 28,
                    border: `1px solid ${openTrigger === key ? 'rgba(4,215,147,0.35)' : 'var(--border)'}`,
                    borderRadius: '6px',
                    background: openTrigger === key ? 'rgba(4,215,147,0.08)' : 'transparent',
                    color: openTrigger === key ? 'var(--caribbean)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'border-color 0.15s, color 0.15s, background 0.15s',
                  }}
                >
                  <Terminal size={11} strokeWidth={1.8} />
                </button>
              </div>

              {/* Manual trigger commands — expands below the button row */}
              {openTrigger === key && (
                <TriggerPanel scenarioKey={key} />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-divider" />
        <button className="ghost-button" onClick={handleReset} disabled={loading === 'reset'}>
          <RotateCcw size={14} strokeWidth={1.5} />
          {loading === 'reset' ? 'Resetting...' : 'Reset Session'}
        </button>
      </div>

    </aside>
  );
}
