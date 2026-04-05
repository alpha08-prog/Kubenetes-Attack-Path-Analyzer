/**
 * MonitoringPanel.tsx — Real-time monitoring log panel.
 *
 * Shows:
 *  • Connection status card (SSE connected / offline, uptime, resources watched)
 *  • Start / Stop Watch API controls
 *  • Real action buttons: Record Baseline, Trigger Analysis, Deploy/Cleanup Scenario
 *  • Live terminal output from script runs
 *  • Session events (SSE stream in this browser session)
 *  • Persisted event history from the backend DB
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Radio, Activity, AlertTriangle, CheckCircle2, XCircle,
  RefreshCw, Play, Square, Clock, Layers, Zap, TrendingUp,
  GitBranch, RotateCcw, Eye, ServerCrash, Wifi, WifiOff,
  Bookmark, Cpu, ShieldAlert, Trash2, Terminal,
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

interface ActionResult {
  status: string;
  message?: string;
  output?: string;
  node_count?: number;
  edge_count?: number;
  run_id?: string;
  sse_clients?: number;
}

interface MonitoringPanelProps {
  liveEvents:       GraphUpdateEvent[];
  isConnected:      boolean;
  monitoringError:  string | null;
  onActionSuccess?: () => void;  // called after any action completes — lets parent switch to Monitor tab
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
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return iso; }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return iso; }
}

// ─── Badges ───────────────────────────────────────────────────────────────────

const EVENT_TYPE_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  RISK_INCREASE:       { label: 'Risk ↑',          color: 'text-red-400 bg-red-500/10 border-red-500/20',           icon: <TrendingUp className="w-3 h-3" /> },
  NEW_ATTACK_PATHS:    { label: 'New Paths',        color: 'text-orange-400 bg-orange-500/10 border-orange-500/20',  icon: <Zap className="w-3 h-3" /> },
  NEW_CYCLES:          { label: 'New Cycles',       color: 'text-purple-400 bg-purple-500/10 border-purple-500/20',  icon: <RotateCcw className="w-3 h-3" /> },
  NEW_RESOURCES:       { label: 'New Resources',    color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',  icon: <Layers className="w-3 h-3" /> },
  GRAPH_UPDATE:        { label: 'Graph Update',     color: 'text-blue-400 bg-blue-500/10 border-blue-500/20',        icon: <GitBranch className="w-3 h-3" /> },
  ANALYSIS_TRIGGERED:  { label: 'Analysis Started', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20', icon: <Cpu className="w-3 h-3" /> },
};

function EventTypeBadge({ type }: { type: string }) {
  const meta = EVENT_TYPE_META[type] ?? {
    label: type, color: 'text-muted-foreground bg-secondary border-border', icon: <Activity className="w-3 h-3" />,
  };
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${meta.color}`}>
      {meta.icon}{meta.label}
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

// ─── Stat tile ────────────────────────────────────────────────────────────────

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

// ─── Status card ─────────────────────────────────────────────────────────────

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
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isConnected
            ? <Wifi className="w-4 h-4 text-emerald-400" />
            : <WifiOff className="w-4 h-4 text-muted-foreground" />}
          <span className="text-xs font-semibold text-foreground">
            {isConnected ? 'SSE Stream Connected' : 'SSE Stream Offline'}
          </span>
          {isConnected && <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />}
        </div>
        <div className="flex gap-1.5">
          <button onClick={onStart} disabled={watching || starting}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 disabled:opacity-40 transition-colors">
            {starting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Start
          </button>
          <button onClick={onStop} disabled={!watching || stopping}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-40 transition-colors">
            {stopping ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
            Stop
          </button>
        </div>
      </div>

      {monitoringError && !isConnected && (
        <p className="text-[11px] text-orange-400 flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3 flex-shrink-0" />{monitoringError}
        </p>
      )}

      <div className="grid grid-cols-2 gap-2">
        <StatTile icon={<Layers className="w-3.5 h-3.5 text-blue-400" />}    label="Resources Watched" value={status?.resources_watched ?? '—'} />
        <StatTile icon={<Activity className="w-3.5 h-3.5 text-emerald-400" />} label="Events Processed"  value={status?.events_processed ?? '—'} />
        <StatTile icon={<Clock className="w-3.5 h-3.5 text-purple-400" />}   label="Uptime"            value={formatUptime(status?.uptime_seconds ?? null)} />
        <StatTile icon={<Eye className="w-3.5 h-3.5 text-orange-400" />}     label="Pending Events"    value={status?.pending_events ?? '—'} />
      </div>

      <div className="flex items-center gap-2 text-[11px] flex-wrap">
        {watching
          ? <span className="flex items-center gap-1 text-emerald-400"><CheckCircle2 className="w-3 h-3" /> K8s Watch API active</span>
          : <span className="flex items-center gap-1 text-muted-foreground"><XCircle className="w-3 h-3" /> Watch API stopped</span>}
        {status?.fallback_active && (
          <span className="flex items-center gap-1 text-yellow-400"><ServerCrash className="w-3 h-3" /> Fallback polling active</span>
        )}
        {status?.last_event_at && (
          <span className="ml-auto text-muted-foreground text-[10px]">Last: {formatTime(status.last_event_at)}</span>
        )}
      </div>
    </div>
  );
}

// ─── Action controls ──────────────────────────────────────────────────────────

type ActionKey = 'baseline' | 'analyze' | 'deploy' | 'cleanup';

interface ActionState {
  loading: boolean;
  result:  ActionResult | null;
  error:   string | null;
}

function ActionButton({
  icon, label, sublabel, color, loading, onClick, disabled,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  color: string;
  loading: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`flex flex-col items-start gap-0.5 w-full px-3 py-2.5 rounded-lg border text-left transition-all disabled:opacity-40 ${color}`}
    >
      <span className="flex items-center gap-1.5 text-[11px] font-semibold">
        {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : icon}
        {loading ? 'Running…' : label}
      </span>
      <span className="text-[10px] opacity-60">{sublabel}</span>
    </button>
  );
}

// ─── Terminal output ──────────────────────────────────────────────────────────

function TerminalOutput({ output, label }: { output: string; label: string }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [output]);

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-secondary/40 border-b border-border">
        <Terminal className="w-3 h-3 text-muted-foreground" />
        <span className="text-[10px] font-medium text-muted-foreground">{label}</span>
      </div>
      <pre
        ref={ref}
        className="text-[10px] font-mono text-emerald-400 bg-background p-3 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed"
      >
        {output || '(no output)'}
      </pre>
    </div>
  );
}

// ─── Session events ───────────────────────────────────────────────────────────

function LiveSessionEvents({ events }: { events: GraphUpdateEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2">
        <Radio className="w-6 h-6 opacity-30" />
        <p className="text-xs">No events received yet in this session.</p>
        <p className="text-[11px] opacity-60">Use the actions above or run kubectl commands to trigger alerts.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {[...events].reverse().map((ev, i) => {
        // Simple acknowledgment events (ANALYSIS_TRIGGERED, etc.)
        if (ev.type !== 'GRAPH_UPDATE') {
          return (
            <div key={i} className="rounded-lg border border-border bg-card/60 p-3 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <EventTypeBadge type={ev.type} />
                <span className="text-[10px] text-muted-foreground flex-shrink-0">{formatTime(ev.timestamp)}</span>
              </div>
              {(ev as any).message && (
                <p className="text-[11px] text-muted-foreground">{(ev as any).message}</p>
              )}
            </div>
          );
        }

        const rd = ev.diff?.risk_delta;
        const pd = ev.diff?.path_delta;
        const cd = ev.diff?.cycle_delta;
        return (
          <div key={i} className="rounded-lg border border-border bg-card/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <EventTypeBadge type="GRAPH_UPDATE" />
                {(rd?.delta ?? 0) > 0  && <EventTypeBadge type="RISK_INCREASE" />}
                {(pd?.delta ?? 0) > 0  && <EventTypeBadge type="NEW_ATTACK_PATHS" />}
                {(cd?.delta ?? 0) > 0  && <EventTypeBadge type="NEW_CYCLES" />}
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0">{formatTime(ev.timestamp)}</span>
            </div>

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

            {((pd?.delta ?? 0) !== 0 || (cd?.delta ?? 0) !== 0) && (
              <div className="flex gap-3 text-[11px]">
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

            {ev.diff?.recommendation && (
              <p className="text-[11px] text-muted-foreground line-clamp-2">{ev.diff.recommendation}</p>
            )}
            <p className="text-[9px] text-muted-foreground/40 font-mono">run:{ev.run_id}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── DB event history ─────────────────────────────────────────────────────────

function DbEventHistory({ events, loading, onRefresh }: {
  events: DbEvent[]; loading: boolean; onRefresh: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Persisted Event Log</span>
        <button onClick={onRefresh} disabled={loading}
          className="text-[10px] flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />Refresh
        </button>
      </div>

      {loading && events.length === 0 ? (
        <div className="flex items-center justify-center py-6"><RefreshCw className="w-4 h-4 animate-spin text-muted-foreground" /></div>
      ) : events.length === 0 ? (
        <div className="text-center py-6 text-muted-foreground text-xs">
          No events recorded yet. Events are persisted when alert thresholds are exceeded.
        </div>
      ) : (
        <div className="space-y-1.5">
          {events.map(ev => (
            <div key={ev.id} className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-card/40 px-3 py-2 hover:border-border transition-colors">
              <div className="flex-shrink-0 pt-0.5"><EventTypeBadge type={ev.event_type} /></div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-foreground leading-snug line-clamp-2">{ev.summary}</p>
                <div className="flex items-center gap-2 mt-1">
                  <SeverityBadge severity={ev.severity} />
                  {ev.triggered_alerts && (
                    <span className="text-[9px] text-muted-foreground">via {ev.triggered_alerts}</span>
                  )}
                </div>
              </div>
              <span className="text-[10px] text-muted-foreground flex-shrink-0 whitespace-nowrap">{formatDateTime(ev.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export default function MonitoringPanel({ liveEvents, isConnected, monitoringError, onActionSuccess }: MonitoringPanelProps) {
  const [status,     setStatus]     = useState<MonitorStatus | null>(null);
  const [dbEvents,   setDbEvents]   = useState<DbEvent[]>([]);
  const [dbLoading,  setDbLoading]  = useState(false);
  const [starting,   setStarting]   = useState(false);
  const [stopping,   setStopping]   = useState(false);
  const [activeView, setActiveView] = useState<'live' | 'history'>('live');

  // Per-action state
  const [actions, setActions] = useState<Record<ActionKey, ActionState>>({
    baseline: { loading: false, result: null, error: null },
    analyze:  { loading: false, result: null, error: null },
    deploy:   { loading: false, result: null, error: null },
    cleanup:  { loading: false, result: null, error: null },
  });

  const setAction = (key: ActionKey, patch: Partial<ActionState>) =>
    setActions(prev => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  // Terminal output (only for scenario actions that return shell output)
  const [terminalOutput, setTerminalOutput] = useState<string | null>(null);
  const [terminalLabel,  setTerminalLabel]  = useState('');

  // After Trigger Analysis fires, wait for the next GRAPH_UPDATE to auto-switch
  // to history so the user sees what was recorded.
  const awaitingGraphUpdate = useRef(false);
  const seenEventCount = useRef(liveEvents.length);

  const fetchStatus = useCallback(async () => {
    try { setStatus((await monitoringApi.status()).data); } catch { /* backend offline */ }
  }, []);

  const fetchDbEvents = useCallback(async () => {
    setDbLoading(true);
    try {
      const res = await monitoringApi.events(50);
      setDbEvents(res.data?.events ?? res.data ?? []);
    } catch { /* ignore */ } finally { setDbLoading(false); }
  }, []);

  useEffect(() => { fetchStatus(); const id = setInterval(fetchStatus, 10_000); return () => clearInterval(id); }, [fetchStatus]);

  // Refresh DB event history whenever a new live event arrives.
  // Also: if Trigger Analysis is pending and a GRAPH_UPDATE arrives,
  // auto-switch to the Event History tab so the user sees what was recorded.
  useEffect(() => {
    if (liveEvents.length === seenEventCount.current) return;
    const newEvents = liveEvents.slice(seenEventCount.current);
    seenEventCount.current = liveEvents.length;

    fetchDbEvents();

    if (awaitingGraphUpdate.current) {
      const hasGraphUpdate = newEvents.some(e => e.type === 'GRAPH_UPDATE');
      if (hasGraphUpdate) {
        awaitingGraphUpdate.current = false;
        setActiveView('history');
      }
    }
  }, [liveEvents, fetchDbEvents]);

  const handleStart = async () => {
    setStarting(true);
    try { await monitoringApi.start(); await fetchStatus(); } catch { /* ignore */ } finally { setStarting(false); }
  };
  const handleStop = async () => {
    setStopping(true);
    try { await monitoringApi.stop(); await fetchStatus(); } catch { /* ignore */ } finally { setStopping(false); }
  };

  const runAction = async (
    key: ActionKey,
    fn: () => Promise<any>,
    label?: string,
    opts: { awaitUpdate?: boolean; reloadGraphAfter?: boolean } = {},
  ) => {
    setAction(key, { loading: true, result: null, error: null });
    if (label) { setTerminalLabel(label); setTerminalOutput(null); }

    // Capture event count BEFORE the API call so SSE events that arrive
    // DURING the call (e.g., ANALYSIS_TRIGGERED broadcast) are not missed.
    const preFnEventCount = liveEvents.length;

    try {
      const res = await fn();
      const data: ActionResult = res.data;
      setAction(key, { loading: false, result: data, error: null });
      if (data.output) { setTerminalOutput(data.output); setTerminalLabel(label ?? ''); }

      // Always switch to live events so the user sees any incoming SSE immediately.
      setActiveView('live');
      // Notify parent (Dashboard) to switch to the Monitor tab so SSE events are visible.
      onActionSuccess?.();

      // For Trigger Analysis / Deploy: flag that the next GRAPH_UPDATE should
      // auto-switch to history. Reset seenEventCount HERE (after fn resolves)
      // so the ANALYSIS_TRIGGERED acknowledgment event that fires during fn
      // doesn't advance the counter before we start watching.
      if (opts.awaitUpdate) {
        seenEventCount.current = preFnEventCount;
        awaitingGraphUpdate.current = true;
      }

      // For Cleanup: reload the graph immediately after the API call returns
      // so the node count drops in one step (instead of relying on Watch API
      // firing twice — once at 149, once at 148).
      if (opts.reloadGraphAfter) {
        // Dispatch a synthetic DOM event so Dashboard.fetchGraph() runs.
        // Small delay lets K8s finish processing the deletes.
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent('graphUpdate', {
            detail: { type: 'CLEANUP_REFRESH', timestamp: new Date().toISOString() }
          }));
        }, 2000);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Request failed';
      setAction(key, { loading: false, result: null, error: msg });
    }
  };

  const isAnyActionRunning = Object.values(actions).some(a => a.loading);

  return (
    <div className="p-4 space-y-4 text-sm">

      {/* Status card */}
      <StatusCard
        status={status}
        isConnected={isConnected}
        monitoringError={monitoringError}
        onStart={handleStart}
        onStop={handleStop}
        starting={starting}
        stopping={stopping}
      />

      {/* ── Real action controls ── */}
      <div className="space-y-2">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
          Real-time Actions
        </p>

        <div className="grid grid-cols-2 gap-2">
          <ActionButton
            icon={<Bookmark className="w-3.5 h-3.5" />}
            label="Record Baseline"
            sublabel="Snapshot current state"
            color="border-blue-500/20 bg-blue-500/5 text-blue-400 hover:bg-blue-500/10"
            loading={actions.baseline.loading}
            disabled={isAnyActionRunning && !actions.baseline.loading}
            onClick={() => runAction('baseline', monitoringApi.recordBaseline)}
          />
          <ActionButton
            icon={<Cpu className="w-3.5 h-3.5" />}
            label="Trigger Analysis"
            sublabel="Rebuild graph + diff + SSE"
            color="border-emerald-500/20 bg-emerald-500/5 text-emerald-400 hover:bg-emerald-500/10"
            loading={actions.analyze.loading}
            disabled={isAnyActionRunning && !actions.analyze.loading}
            onClick={() => runAction('analyze', monitoringApi.triggerAnalysis, undefined, { awaitUpdate: true })}
          />
          <ActionButton
            icon={<ShieldAlert className="w-3.5 h-3.5" />}
            label="Deploy Scenario"
            sublabel="Runs vulnerable script on cluster"
            color="border-orange-500/20 bg-orange-500/5 text-orange-400 hover:bg-orange-500/10"
            loading={actions.deploy.loading}
            disabled={isAnyActionRunning && !actions.deploy.loading}
            onClick={() => runAction('deploy', monitoringApi.runScenario, 'deploy_vulnerable_scenerio.sh', { awaitUpdate: true })}
          />
          <ActionButton
            icon={<Trash2 className="w-3.5 h-3.5" />}
            label="Cleanup Scenario"
            sublabel="Remove deployed resources"
            color="border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/10"
            loading={actions.cleanup.loading}
            disabled={isAnyActionRunning && !actions.cleanup.loading}
            onClick={() => runAction('cleanup', monitoringApi.cleanupScenario, 'deploy_vulnerable_scenerio.sh --cleanup', { reloadGraphAfter: true })}
          />
        </div>

        {/* Inline status messages */}
        {Object.entries(actions).map(([key, state]) => {
          if (!state.result && !state.error) return null;
          const isErr = !!state.error;
          return (
            <div key={key} className={`text-[11px] px-3 py-2 rounded-md flex items-start gap-2 ${isErr ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
              {isErr
                ? <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                : <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />}
              <div className="min-w-0">
                {isErr ? state.error : (state.result?.message ?? state.result?.status)}
                {state.result?.run_id && (
                  <span className="ml-2 font-mono text-[9px] opacity-60">run:{state.result.run_id}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Terminal output */}
      {terminalOutput !== null && (
        <TerminalOutput output={terminalOutput} label={terminalLabel} />
      )}

      {/* View toggle */}
      <div className="flex gap-1 p-0.5 bg-secondary/40 rounded-lg">
        {(['live', 'history'] as const).map(v => (
          <button key={v} onClick={() => setActiveView(v)}
            className={`flex-1 text-[11px] py-1.5 rounded-md font-medium transition-colors ${activeView === v ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
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

      {/* Content */}
      {activeView === 'live'
        ? <LiveSessionEvents events={liveEvents} />
        : <DbEventHistory events={dbEvents} loading={dbLoading} onRefresh={fetchDbEvents} />}
    </div>
  );
}
