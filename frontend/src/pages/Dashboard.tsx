import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, RefreshCw, Play, Network, GitBranch,
  AlertTriangle, RotateCcw, Activity, Radio,
} from 'lucide-react';
import { useGraph } from '@/hooks/useGraph';
import { useAnalysis } from '@/hooks/useAnalysis';
import GraphCanvas from '@/components/GraphCanvas';
import StatCard from '@/components/StatCard';
import ThreatScoreCard from '@/components/ThreatScoreCard';
import AttackPathPanel from '@/components/AttackPathPanel';
import BlastRadiusPanel from '@/components/BlastRadiusPanel';
import CyclesPanel from '@/components/CyclesPanel';
import CriticalNodeTable from '@/components/CriticalNodeTable';
import SimulationPanel from '@/components/SimulationPanel';
import SimulationModal from '@/components/SimulationModal';
import NarratorPanel from '@/components/NarratorPanel';
import DiffPanel from '@/components/DiffPanel';
import MonitoringPanel from '@/components/MonitoringPanel';
import { ThemeToggle } from '@/components/theme-toggle';
import { useMonitoring, type GraphUpdateEvent } from '@/hooks/useMonitoring';

type OverlayMode = 'default' | 'attack' | 'blast' | 'cycle';
type Tab = 'attack' | 'blast' | 'cycles' | 'simulation' | 'diff' | 'monitor';

const OVERLAY_MODES: { mode: OverlayMode; label: string }[] = [
  { mode: 'default', label: 'Default' },
  { mode: 'attack',  label: 'Attack Path' },
  { mode: 'blast',   label: 'Blast Radius' },
  { mode: 'cycle',   label: 'Cycles' },
];

const TABS: { key: Tab; label: string }[] = [
  { key: 'attack',     label: 'Attack Path' },
  { key: 'blast',      label: 'Blast Radius' },
  { key: 'cycles',     label: 'Cycles & Critical' },
  { key: 'simulation', label: 'Simulation' },
  { key: 'diff',       label: 'Diff' },
  { key: 'monitor',    label: 'Monitor' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { graphData, summary, loading: graphLoading, reload, fetchGraph } = useGraph();
  const analysis = useAnalysis();
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('default');
  const [activeTab, setActiveTab] = useState<Tab>('attack');
  const [simModal, setSimModal] = useState<any>(null);
  const [simSource, setSimSource] = useState('');
  const [simTarget, setSimTarget] = useState('');

  // ── Real-time monitoring ───────────────────────────────────────────────────
  const { isConnected: monitorConnected, monitoringError, liveEvents } = useMonitoring();
  const [liveAlert, setLiveAlert]   = useState<GraphUpdateEvent | null>(null);
  const alertTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const nodes = graphData?.nodes || [];

  const handleContextAction = useCallback((action: string, nodeId: string) => {
    if (action === 'set-source') setSimSource(nodeId);
    if (action === 'set-target') setSimTarget(nodeId);
    if (action === 'blast-radius') {
      setActiveTab('blast');
      analysis.analyzeBlast(nodeId, 3);
    }
    if (action === 'simulate-removal') {
      setActiveTab('simulation');
    }
  }, [analysis]);

  const handleCriticalSimulate = async (nodeId: string) => {
    const src = simSource || 'pod:default:web-server';
    const tgt = simTarget || 'database:default:billing-db';
    const result = await analysis.runSimulation(nodeId, src, tgt);
    if (result) setSimModal(result);
  };

  useEffect(() => {
    if (summary && summary.total_nodes > 0 && !analysis.threatScore) {
      analysis.fetchFullAnalysis();
    }
  }, [summary]);

  // ── Handle real-time graph update events from useMonitoring ──────────────
  const graphLoadingRef = useRef(graphLoading);
  useEffect(() => {
    graphLoadingRef.current = graphLoading;
    // If a CLEANUP_REFRESH arrived while a fetch was in-flight, it was deferred.
    // Now that loading has settled to false, fire the guaranteed fetch.
    if (!graphLoading && cleanupPendingRef.current) {
      cleanupPendingRef.current = false;
      fetchGraph();
    }
  }, [graphLoading, fetchGraph]);

  const pendingRefreshRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tracks whether a CLEANUP_REFRESH needs a guaranteed fetch once loading settles.
  const cleanupPendingRef = useRef(false);

  useEffect(() => {
    const handleGraphUpdate = (e: Event) => {
      const update = (e as CustomEvent<GraphUpdateEvent>).detail;

      // Show alert banner only for real security events (not housekeeping refreshes)
      if (update.type === 'GRAPH_UPDATE') {
        setLiveAlert(update);
        if (alertTimer.current) clearTimeout(alertTimer.current);
        alertTimer.current = setTimeout(() => setLiveAlert(null), 8000);
      }

      // Debounce: cancel any pending refresh and schedule a new one.
      // This batches rapid SSE events (e.g. Watch API firing for each deleted resource)
      // into a single fetch call so we only ever see the final stable graph state.
      if (pendingRefreshRef.current) clearTimeout(pendingRefreshRef.current);

      if (update.type === 'CLEANUP_REFRESH') {
        // Mark that a cleanup fetch is required — don't let it get dropped.
        // If another fetch is in-flight right now, the useEffect below will
        // pick this up once loading finishes.
        cleanupPendingRef.current = true;
        if (!graphLoadingRef.current) {
          cleanupPendingRef.current = false;
          fetchGraph();
        }
        return;
      }

      // GRAPH_UPDATE and other event types: debounce with 500ms.
      pendingRefreshRef.current = setTimeout(() => {
        // Read loading state from ref so this closure is never stale.
        if (!graphLoadingRef.current) fetchGraph();
      }, 500);
    };

    window.addEventListener('graphUpdate', handleGraphUpdate);
    return () => {
      window.removeEventListener('graphUpdate', handleGraphUpdate);
      if (alertTimer.current) clearTimeout(alertTimer.current);
      if (pendingRefreshRef.current) clearTimeout(pendingRefreshRef.current);
    };
  // fetchGraph is stable (empty useCallback deps) — safe to omit from deps.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchGraph]);

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="flex-shrink-0 flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 md:px-6 py-1.5 border-b border-border bg-card/80">
        {/* Left: branding */}
        <div className="flex items-center gap-1.5 sm:gap-2 md:gap-3 min-w-0 flex-1">
          {/* Live indicator */}
          <span className="hidden sm:flex items-center gap-1 text-[8px] md:text-[10px] font-semibold text-emerald-400 tracking-widest uppercase flex-shrink-0">
            <span className="w-1 h-1 md:w-1.5 md:h-1.5 rounded-full bg-emerald-400 animate-live" />
            Live
          </span>

          <div className="w-px h-3 md:h-4 bg-border hidden sm:block flex-shrink-0" />

          <Shield className="w-4 md:w-5 h-4 md:h-5 text-primary flex-shrink-0" />
          <h1 className="text-xs md:text-sm lg:text-base font-bold text-foreground tracking-tight truncate">
            Attack Path Analyzer
          </h1>
          <span className="hidden md:inline text-[10px] lg:text-[11px] bg-primary/15 text-primary border border-primary/20 px-1.5 md:px-2 py-0.5 rounded-full font-medium flex-shrink-0">
            nokia-telecom-cluster
          </span>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <button
            onClick={reload}
            disabled={graphLoading}
            className="flex items-center gap-1 sm:gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-colors disabled:opacity-50"
            title="Reload graph data"
          >
            <RefreshCw className={`w-3 sm:w-3.5 h-3 sm:h-3.5 ${graphLoading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Reload</span>
          </button>
          <button
            onClick={() => navigate('/cve-feed')}
            className="flex items-center gap-1 sm:gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-colors"
            title="View Live CVE Feed"
          >
            <AlertTriangle className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-orange-400" />
            <span className="hidden sm:inline">CVE Feed</span>
          </button>
          <button
            onClick={() => navigate('/temporal')}
            className="flex items-center gap-1 sm:gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-colors"
            title="Temporal Analysis — track graph changes over time"
          >
            <Activity className="w-3 sm:w-3.5 h-3 sm:h-3.5 text-blue-400" />
            <span className="hidden sm:inline">Temporal</span>
          </button>
          {/* Real-time monitoring status */}
          <div
            className={`hidden sm:flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium border ${
              monitorConnected
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-secondary text-muted-foreground border-border'
            }`}
            title={monitorConnected ? 'Real-time monitoring active' : monitoringError || 'Monitoring offline'}
          >
            <Radio className={`w-3 h-3 ${monitorConnected ? 'animate-pulse' : 'opacity-40'}`} />
            <span>{monitorConnected ? 'Monitoring' : 'Monitor off'}</span>
          </div>

          <ThemeToggle />

          <button
            onClick={() => navigate('/demo')}
            className="flex items-center gap-1 sm:gap-1.5 bg-primary hover:opacity-90 text-primary-foreground px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-opacity"
            title="Start interactive demo"
          >
            <Play className="w-3 sm:w-3.5 h-3 sm:h-3.5" />
            <span className="hidden sm:inline">Demo</span>
          </button>
        </div>
      </header>

      {/* ── Metrics Bar ────────────────────────────────────────── */}
      <div className="flex-shrink-0 flex gap-2 px-3 sm:px-6 py-1 border-b border-border/60 overflow-x-auto scrollbar-thin text-xs">
        {/* Threat Score — responsive width */}
        <div className="w-32 sm:w-36 md:w-40 flex-shrink-0">
          <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
        </div>

        {/* Stat cards — evenly distribute space across all cards */}
        <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-1.5 sm:gap-2 min-w-0">
          <StatCard
            title="Total Nodes"
            value={summary?.total_nodes ?? '—'}
            icon={<Network className="w-3.5 h-3.5" />}
            color="#378ADD"
            loading={graphLoading}
          />
          <StatCard
            title="Total Edges"
            value={summary?.total_edges ?? '—'}
            icon={<GitBranch className="w-3.5 h-3.5" />}
            color="#1D9E75"
            loading={graphLoading}
          />
          <StatCard
            title="Critical Findings"
            value={summary?.critical_findings ?? '—'}
            icon={<AlertTriangle className="w-3.5 h-3.5" />}
            color="#E24B4A"
            loading={graphLoading}
          />
          <StatCard
            title="Cycles Detected"
            value={summary?.cycles_detected ?? '—'}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            color="#7F77DD"
            loading={graphLoading}
          />
        </div>
      </div>

      {/* ── Live Alert Banner (auto-dismiss after 8s) ──────────────── */}
      {liveAlert && (
        <div className="flex-shrink-0 mx-3 sm:mx-6 mt-1 flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2.5 text-xs animate-in slide-in-from-top-2 duration-300">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-red-400">
              Security Change Detected
              {liveAlert.diff?.risk_delta?.delta > 0 && (
                <span className="ml-2 text-red-300">
                  Risk +{liveAlert.diff.risk_delta.delta.toFixed(1)} ({liveAlert.diff.risk_delta.after.toFixed(1)})
                </span>
              )}
            </p>
            <p className="text-muted-foreground truncate">
              {liveAlert.diff?.path_delta?.delta > 0 && (
                <span className="mr-3">{liveAlert.diff.path_delta.delta} new attack path(s)</span>
              )}
              {liveAlert.diff?.cycle_delta?.delta > 0 && (
                <span className="mr-3">{liveAlert.diff.cycle_delta.delta} new cycle(s)</span>
              )}
              {liveAlert.diff?.recommendation?.slice(0, 120)}
            </p>
          </div>
          <button
            onClick={() => setLiveAlert(null)}
            className="text-muted-foreground hover:text-foreground flex-shrink-0 text-xs"
          >✕</button>
        </div>
      )}

      {/* ── Main Content ────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 px-3 sm:px-6 py-2.5 gap-2.5">

        {/* Left — Graph panel (70%) */}
        <div className="w-full md:w-[70%] flex flex-col min-h-0 rounded-xl border border-border bg-card overflow-hidden">
          {/* Graph panel header */}
          <div className="flex-shrink-0 flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-border/70">
            <div className="flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs font-semibold text-foreground">Network Topology</span>
              {summary && (
                <span className="text-[9px] md:text-[10px] text-muted-foreground truncate">
                  {summary.total_nodes} nodes · {summary.total_edges} edges
                </span>
              )}
            </div>

            {/* Overlay mode pills */}
            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-secondary/60">
              {OVERLAY_MODES.map(m => (
                <button
                  key={m.mode}
                  onClick={() => setOverlayMode(m.mode)}
                  className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-all ${
                    overlayMode === m.mode
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Graph canvas */}
          <div className="flex-1 min-h-0">
            <GraphCanvas
              graphData={graphData}
              attackPath={analysis.attackPath}
              blastRadius={analysis.blastRadius}
              cycles={analysis.cycles}
              overlayMode={overlayMode}
              onContextAction={handleContextAction}
            />
          </div>
        </div>

        {/* Right — Analysis panel (30%) */}
        <div className="w-full md:w-[30%] flex flex-col min-h-0 gap-2.5">

          {/* Analysis tabs panel */}
          <div className="flex flex-col min-h-0 flex-1 rounded-xl border border-border bg-card overflow-hidden">
            {/* Panel header */}
            <div className="flex-shrink-0 px-4 py-2.5 border-b border-border/70">
              <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-primary" />
                Security Analysis
              </span>
            </div>

            {/* Tab strip */}
            <div className="flex-shrink-0 flex border-b border-border/70 bg-secondary/20">
              {TABS.map(t => (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`flex-1 text-[11px] py-2.5 font-medium transition-colors relative ${
                    activeTab === t.key
                      ? 'text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span className="inline-flex items-center justify-center gap-1">
                    {t.label}
                    {/* Live event count badge on Monitor tab */}
                    {t.key === 'monitor' && liveEvents.length > 0 && (
                      <span className="w-4 h-4 rounded-full bg-red-500 text-white text-[8px] font-bold flex items-center justify-center">
                        {liveEvents.length > 9 ? '9+' : liveEvents.length}
                      </span>
                    )}
                    {/* Pulse dot when monitoring is connected */}
                    {t.key === 'monitor' && monitorConnected && liveEvents.length === 0 && (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    )}
                  </span>
                  {activeTab === t.key && (
                    <span className="absolute bottom-0 left-0 right-0 h-1 bg-primary" />
                  )}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              {activeTab === 'attack' && (
                <AttackPathPanel
                  nodes={nodes}
                  attackPath={analysis.attackPath}
                  loading={analysis.loading.attack}
                  onFindPath={analysis.findAttackPath}
                  onAutoDetect={analysis.autoAttackPath}
                  onShowOnGraph={() => setOverlayMode('attack')}
                />
              )}
              {activeTab === 'blast' && (
                <BlastRadiusPanel
                  nodes={nodes}
                  blastRadius={analysis.blastRadius}
                  loading={analysis.loading.blast}
                  onAnalyze={analysis.analyzeBlast}
                  onShowOnGraph={() => setOverlayMode('blast')}
                />
              )}
              {activeTab === 'cycles' && (
                <div className="divide-y divide-border">
                  <CyclesPanel
                    cycles={analysis.cycles}
                    loading={analysis.loading.cycles}
                    onFetch={analysis.fetchCycles}
                  />
                  <CriticalNodeTable
                    criticalNodes={analysis.criticalNodes}
                    loading={analysis.loading.critical}
                    onFetch={analysis.fetchCriticalNodes}
                    onSimulate={handleCriticalSimulate}
                  />
                </div>
              )}
              {activeTab === 'simulation' && (
                <SimulationPanel
                  nodes={nodes}
                  criticalNodes={analysis.criticalNodes}
                  simulation={analysis.simulation}
                  loading={analysis.loading.simulation}
                  onSimulate={analysis.runSimulation}
                />
              )}
              {activeTab === 'diff' && <DiffPanel />}
              {activeTab === 'monitor' && (
                <MonitoringPanel
                  liveEvents={liveEvents}
                  isConnected={monitorConnected}
                  monitoringError={monitoringError}
                  onActionSuccess={() => setActiveTab('monitor')}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── AI Narrator ─────────────────────────────────────────── */}
      <NarratorPanel
        report={analysis.report}
        loading={analysis.loading.report}
        onFetchReport={analysis.fetchReport}
        error={analysis.errors.report}
      />

      {/* ── Simulation Modal ─────────────────────────────────────── */}
      {simModal && (
        <SimulationModal
          simulation={simModal}
          onClose={() => setSimModal(null)}
        />
      )}
    </div>
  );
}
