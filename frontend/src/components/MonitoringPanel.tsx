/**
 * MonitoringPanel.tsx — Real-time monitoring log panel.
 *
 * Shows:
 *  • Connection status card (SSE connected / offline, uptime, resources watched)
 *  • Start / Stop controls
 *  • Live session events — events received in the current browser session via SSE
 *  • Persistent event history — last N events fetched from the backend DB
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Radio, Activity, AlertTriangle, CheckCircle2, XCircle,
  RefreshCw, Play, Square, Clock, Layers, Zap, TrendingUp,
  GitBranch, RotateCcw, Eye, ServerCrash, Wifi, WifiOff,
  FlaskConical, Terminal, ChevronDown, ChevronRight,
} from 'lucide-react';
import { monitoringApi, type GraphUpdateEvent } from '@/hooks/useMonitoring';

// ─── Types ────────────────────────────────────────────────────────────────────

interface MonitorStatus {
  watching:          boolean;
  fallback_active:   boolean;
  started_at:        string | null;
  uptime_seconds:    number | null;
  cluster:           string;
  debounce_ms:       number;
  alert_threshold:   number;
  resources_watched: number;
  events_processed:  number;
  pending_events:    number;
  last_event_at:     string | null;
  sse_clients?:      number;
}

interface DbEvent {
  id:               number;
  run_id:           string;
  event_type:       string;
  resource_type:    string | null;
  severity:         string;
  summary:          string;
  triggered_alerts: string | null;
  created_at:       string;
}

interface MonitoringPanelProps {
  /** SSE-connected session events pushed from useMonitoring hook */
  liveEvents: GraphUpdateEvent[];
  isConnected: boolean;
  monitoringError: string | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatUptime(seconds: number | null): string {
  if (seconds === null || seconds < 0) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ${seconds % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

const EVENT_TYPE_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  RISK_INCREASE:    { label: 'Risk ↑',     color: 'text-red-400 bg-red-500/10 border-red-500/20',      icon: <TrendingUp className="w-3 h-3" /> },
  NEW_ATTACK_PATHS: { label: 'New Paths',  color: 'text-orange-400 bg-orange-500/10 border-orange-500/20', icon: <Zap className="w-3 h-3" /> },
  NEW_CYCLES:       { label: 'New Cycles', color: 'text-purple-400 bg-purple-500/10 border-purple-500/20', icon: <RotateCcw className="w-3 h-3" /> },
  GRAPH_UPDATE:     { label: 'Graph Update', color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',  icon: <GitBranch className="w-3 h-3" /> },
};

function EventTypeBadge({ type }: { type: string }) {
  const meta = EVENT_TYPE_META[type] ?? {
    label: type,
    color: 'text-muted-foreground bg-secondary border-border',
    icon: <Activity className="w-3 h-3" />,
  };
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${meta.color}`}>
      {meta.icon}
      {meta.label}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10',
    high:     'text-orange-400 bg-orange-500/10',
    medium:   'text-yellow-400 bg-yellow-500/10',
    low:      'text-green-400 bg-green-500/10',
  };
  return (
    <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${colors[severity?.toLowerCase()] ?? 'text-muted-foreground bg-secondary'}`}>
      {severity || '—'}
    </span>
  );
}

// ─── Status Card ─────────────────────────────────────────────────────────────

function StatusCard({
  status, isConnected, monitoringError, onStart, onStop, starting, stopping,
}: {
  status: MonitorStatus | null;
  isConnected: boolean;
  monitoringError: string | null;
  onStart: () => void;
  onStop: () => void;
  starting: boolean;
  stopping: boolean;
}) {
  const watching = status?.watching ?? false;

  return (
    <div className="rounded-lg border border-border bg-card/60 p-3 space-y-3">
      {/* Top row: connection state */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isConnected ? (
            <Wifi className="w-4 h-4 text-emerald-400" />
          ) : (
            <WifiOff className="w-4 h-4 text-muted-foreground" />
          )}
          <span className="text-xs font-semibold text-foreground">
            {isConnected ? 'SSE Stream Connected' : 'SSE Stream Offline'}
          </span>
          {isConnected && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </div>

        {/* Start / Stop */}
        <div className="flex gap-1.5">
          <button
            onClick={onStart}
            disabled={watching || starting}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 disabled:opacity-40 transition-colors"
          >
            {starting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Start
          </button>
          <button
            onClick={onStop}
            disabled={!watching || stopping}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-40 transition-colors"
          >
            {stopping ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
            Stop
          </button>
        </div>
      </div>

      {/* Error message */}
      {monitoringError && !isConnected && (
        <p className="text-[11px] text-orange-400 flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" />
          {monitoringError}
        </p>
      )}

      {/* Stat grid */}
      <div className="grid grid-cols-2 gap-2">
        <StatTile
          icon={<Layers className="w-3.5 h-3.5 text-blue-400" />}
          label="Resources Watched"
          value={status?.resources_watched ?? '—'}
        />
        <StatTile
          icon={<Activity className="w-3.5 h-3.5 text-emerald-400" />}
          label="Events Processed"
          value={status?.events_processed ?? '—'}
        />
        <StatTile
          icon={<Clock className="w-3.5 h-3.5 text-purple-400" />}
          label="Uptime"
          value={formatUptime(status?.uptime_seconds ?? null)}
        />
        <StatTile
          icon={<Eye className="w-3.5 h-3.5 text-orange-400" />}
          label="Pending Events"
          value={status?.pending_events ?? '—'}
        />
      </div>

      {/* Watch state + fallback */}
      <div className="flex items-center gap-2 text-[11px]">
        {watching ? (
          <span className="flex items-center gap-1 text-emerald-400">
            <CheckCircle2 className="w-3 h-3" /> K8s Watch API active
          </span>
        ) : (
          <span className="flex items-center gap-1 text-muted-foreground">
            <XCircle className="w-3 h-3" /> Watch API stopped
          </span>
        )}
        {status?.fallback_active && (
          <span className="flex items-center gap-1 text-yellow-400">
            <ServerCrash className="w-3 h-3" /> Fallback polling active
          </span>
        )}
        {status?.last_event_at && (
          <span className="ml-auto text-muted-foreground text-[10px]">
            Last: {formatTime(status.last_event_at)}
          </span>
        )}
      </div>
    </div>
  );
}

function StatTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 bg-secondary/30 rounded-md p-2">
      {icon}
      <div className="min-w-0">
        <div className="text-[9px] text-muted-foreground uppercase tracking-wide truncate">{label}</div>
        <div className="text-xs font-semibold text-foreground">{value}</div>
      </div>
    </div>
  );
}

// ─── Live Session Events ──────────────────────────────────────────────────────

function LiveSessionEvents({ events }: { events: GraphUpdateEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground gap-2">
        <Radio className="w-6 h-6 opacity-30" />
        <p className="text-xs">No events received in this session.</p>
        <p className="text-[11px] opacity-60">Deploy or modify K8s resources to trigger alerts.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {[...events].reverse().map((ev, i) => {
        const rd = ev.diff?.risk_delta;
        const pd = ev.diff?.path_delta;
        const cd = ev.diff?.cycle_delta;
        return (
          <div key={i} className="rounded-lg border border-border bg-card/60 p-3 space-y-1.5">
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <EventTypeBadge type="GRAPH_UPDATE" />
                {rd?.delta > 0 && <EventTypeBadge type="RISK_INCREASE" />}
                {(pd?.delta ?? 0) > 0 && <EventTypeBadge type="NEW_ATTACK_PATHS" />}
                {(cd?.delta ?? 0) > 0 && <EventTypeBadge type="NEW_CYCLES" />}
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0">
                {formatTime(ev.timestamp)}
              </span>
            </div>

            {/* Risk row */}
            {rd && (
              <div className="flex items-center gap-3 text-[11px]">
                <span className="text-muted-foreground">Risk</span>
                <span className="font-mono text-foreground">{rd.before?.toFixed(1)}</span>
                <span className="text-muted-foreground">→</span>
                <span className={`font-mono font-semibold ${rd.delta > 0 ? 'text-red-400' : rd.delta < 0 ? 'text-emerald-400' : 'text-foreground'}`}>
                  {rd.after?.toFixed(1)}
                </span>
                {rd.delta !== 0 && (
                  <span className={`text-[10px] font-bold ${rd.delta > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                    {rd.delta > 0 ? '+' : ''}{rd.delta?.toFixed(1)} ({rd.delta_pct?.toFixed(0)}%)
                  </span>
                )}
                <SeverityBadge severity={rd.severity_after} />
              </div>
            )}

            {/* Path / Cycle deltas */}
            {((pd?.delta ?? 0) !== 0 || (cd?.delta ?? 0) !== 0) && (
              <div className="flex gap-3 text-[11px] text-muted-foreground">
                {pd && pd.delta !== 0 && (
                  <span className={pd.delta > 0 ? 'text-orange-400' : 'text-emerald-400'}>
                    {pd.delta > 0 ? `+${pd.delta}` : pd.delta} attack path(s)
                  </span>
                )}
                {cd && cd.delta !== 0 && (
                  <span className={cd.delta > 0 ? 'text-purple-400' : 'text-emerald-400'}>
                    {cd.delta > 0 ? `+${cd.delta}` : cd.delta} cycle(s)
                  </span>
                )}
              </div>
            )}

            {/* Recommendation */}
            {ev.diff?.recommendation && (
              <p className="text-[11px] text-muted-foreground line-clamp-2">
                {ev.diff.recommendation}
              </p>
            )}

            {/* Run ID */}
            <p className="text-[9px] text-muted-foreground/50 font-mono">run:{ev.run_id}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── DB Event History ─────────────────────────────────────────────────────────

function DbEventHistory({ events, loading, onRefresh }: {
  events: DbEvent[];
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
          Persisted Event Log
        </span>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="text-[10px] flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {loading && events.length === 0 ? (
        <div className="flex items-center justify-center py-6">
          <RefreshCw className="w-4 h-4 animate-spin text-muted-foreground" />
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-6 text-muted-foreground text-xs">
          No events recorded yet. Events are written here when alert thresholds are exceeded.
        </div>
      ) : (
        <div className="space-y-1.5">
          {events.map(ev => (
            <div
              key={ev.id}
              className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-card/40 px-3 py-2 hover:border-border transition-colors"
            >
              {/* Badge + type */}
              <div className="flex-shrink-0 pt-0.5">
                <EventTypeBadge type={ev.event_type} />
              </div>

              {/* Main content */}
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-foreground leading-snug line-clamp-2">
                  {ev.summary}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <SeverityBadge severity={ev.severity} />
                  {ev.triggered_alerts && (
                    <span className="text-[9px] text-muted-foreground">
                      via {ev.triggered_alerts}
                    </span>
                  )}
                </div>
              </div>

              {/* Time */}
              <span className="text-[10px] text-muted-foreground flex-shrink-0 whitespace-nowrap">
                {formatDateTime(ev.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Minikube Quick-Start Guide ───────────────────────────────────────────────

function MinikubeGuide() {
  const [open, setOpen] = useState(false);

  const steps = [
    { label: 'Start minikube', cmd: 'minikube start' },
    { label: 'Verify cluster is up', cmd: 'kubectl cluster-info' },
    { label: 'Restart backend (MOCK_MODE=false required)', cmd: 'cd Attack_path_analyzer/backend\nuvicorn app.main:app --reload --port 8000' },
    { label: 'Trigger a risk event — deploy a pod', cmd: 'kubectl create deployment monitor-test --image=nginx' },
    { label: 'Trigger a critical alert — bind admin role', cmd: 'kubectl create rolebinding risky-binding \\\n  --clusterrole=admin \\\n  --serviceaccount=default:default' },
    { label: 'Clean up after testing', cmd: 'kubectl delete deployment monitor-test\nkubectl delete rolebinding risky-binding' },
  ];

  return (
    <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
        onClick={() => setOpen(o => !o)}
      >
        <span className="flex items-center gap-2 text-[11px] font-semibold text-blue-400">
          <Terminal className="w-3.5 h-3.5" />
          Minikube Quick-Start Guide
        </span>
        {open ? <ChevronDown className="w-3.5 h-3.5 text-blue-400" /> : <ChevronRight className="w-3.5 h-3.5 text-blue-400" />}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2.5 border-t border-blue-500/20 pt-2.5">
          <p className="text-[11px] text-muted-foreground">
            Run these commands in your terminal. Events will appear in <strong>Session Events</strong> within 2–5 seconds.
          </p>
          {steps.map((step, i) => (
            <div key={i} className="space-y-1">
              <p className="text-[10px] text-muted-foreground font-medium">
                {i + 1}. {step.label}
              </p>
              <pre className="text-[10px] bg-background border border-border rounded-md px-2.5 py-1.5 text-emerald-400 font-mono overflow-x-auto whitespace-pre-wrap">
                {step.cmd}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ─── Main Panel ───────────────────────────────────────────────────────────────

export default function MonitoringPanel({
  liveEvents,
  isConnected,
  monitoringError,
}: MonitoringPanelProps) {
  const [status, setStatus]           = useState<MonitorStatus | null>(null);
  const [dbEvents, setDbEvents]       = useState<DbEvent[]>([]);
  const [dbLoading, setDbLoading]     = useState(false);
  const [starting, setStarting]       = useState(false);
  const [stopping, setStopping]       = useState(false);
  const [testFiring, setTestFiring]   = useState(false);
  const [testResult, setTestResult]   = useState<string | null>(null);
  const [activeView, setActiveView]   = useState<'live' | 'history'>('live');

  // Fetch backend status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await monitoringApi.status();
      setStatus(res.data);
    } catch {
      // ignore — backend may be offline
    }
  }, []);

  // Fetch DB event history
  const fetchDbEvents = useCallback(async () => {
    setDbLoading(true);
    try {
      const res = await monitoringApi.events(50);
      setDbEvents(res.data?.events ?? res.data ?? []);
    } catch {
      // ignore
    } finally {
      setDbLoading(false);
    }
  }, []);

  // Poll status every 10 s
  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 10_000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // Load DB events on mount + when new live event arrives
  useEffect(() => {
    fetchDbEvents();
  }, [fetchDbEvents, liveEvents.length]);

  const handleStart = async () => {
    setStarting(true);
    try {
      await monitoringApi.start();
      await fetchStatus();
    } catch {
      // ignore
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      await monitoringApi.stop();
      await fetchStatus();
    } catch {
      // ignore
    } finally {
      setStopping(false);
    }
  };

  const handleTestEvent = async () => {
    setTestFiring(true);
    setTestResult(null);
    try {
      const res = await monitoringApi.testEvent();
      const clients = res.data?.sse_clients ?? 0;
      setTestResult(
        clients > 0
          ? `✓ Test event sent to ${clients} client(s). Check Session Events ↑`
          : '⚠ No SSE clients connected. Make sure this tab is open and connected.',
      );
      // Switch to session events so the user sees it immediately
      setActiveView('live');
    } catch (err: any) {
      setTestResult(`✗ Error: ${err?.message ?? 'Failed to send test event'}`);
    } finally {
      setTestFiring(false);
      setTimeout(() => setTestResult(null), 6000);
    }
  };

  return (
    <div className="p-4 space-y-4 text-sm">

      {/* ── Status Card ── */}
      <StatusCard
        status={status}
        isConnected={isConnected}
        monitoringError={monitoringError}
        onStart={handleStart}
        onStop={handleStop}
        starting={starting}
        stopping={stopping}
      />

      {/* ── Test Event ── */}
      <div className="space-y-2">
        <button
          onClick={handleTestEvent}
          disabled={testFiring}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-dashed border-border hover:border-primary/40 text-[11px] font-medium text-muted-foreground hover:text-primary transition-colors disabled:opacity-50"
        >
          {testFiring
            ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            : <FlaskConical className="w-3.5 h-3.5" />}
          {testFiring ? 'Sending test event…' : 'Send Test Event  (no K8s changes needed)'}
        </button>
        {testResult && (
          <p className={`text-[11px] text-center px-2 py-1.5 rounded-md ${
            testResult.startsWith('✓')
              ? 'text-emerald-400 bg-emerald-500/10'
              : testResult.startsWith('⚠')
              ? 'text-yellow-400 bg-yellow-500/10'
              : 'text-red-400 bg-red-500/10'
          }`}>
            {testResult}
          </p>
        )}
      </div>

      {/* ── Minikube guide ── */}
      <MinikubeGuide />

      {/* ── View toggle ── */}
      <div className="flex gap-1 p-0.5 bg-secondary/40 rounded-lg">
        {(['live', 'history'] as const).map(v => (
          <button
            key={v}
            onClick={() => setActiveView(v)}
            className={`flex-1 text-[11px] py-1.5 rounded-md font-medium transition-colors ${
              activeView === v
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {v === 'live' ? (
              <span className="flex items-center justify-center gap-1">
                <Radio className="w-3 h-3" />
                Session Events {liveEvents.length > 0 && `(${liveEvents.length})`}
              </span>
            ) : (
              <span className="flex items-center justify-center gap-1">
                <Clock className="w-3 h-3" />
                Event History {dbEvents.length > 0 && `(${dbEvents.length})`}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      {activeView === 'live' ? (
        <LiveSessionEvents events={liveEvents} />
      ) : (
        <DbEventHistory
          events={dbEvents}
          loading={dbLoading}
          onRefresh={fetchDbEvents}
        />
      )}
    </div>
  );
}
