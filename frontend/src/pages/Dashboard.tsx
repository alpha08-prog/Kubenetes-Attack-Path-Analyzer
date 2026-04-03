import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, RefreshCw, Play, Network, GitBranch,
  AlertTriangle, RotateCcw, Activity,
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
import LiveCveFeedPanel from '@/components/LiveCveFeedPanel';

type OverlayMode = 'default' | 'attack' | 'blast' | 'cycle';
type Tab = 'attack' | 'blast' | 'cycles' | 'simulation';

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
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { graphData, summary, loading: graphLoading, reload } = useGraph();
  const analysis = useAnalysis();
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('default');
  const [activeTab, setActiveTab] = useState<Tab>('attack');
  const [simModal, setSimModal] = useState<any>(null);
  const [simSource, setSimSource] = useState('');
  const [simTarget, setSimTarget] = useState('');

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

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="flex-shrink-0 flex flex-wrap items-center justify-between gap-2 px-4 sm:px-6 py-3 border-b border-border bg-card/80">
        {/* Left: branding */}
        <div className="flex items-center gap-3">
          {/* Live indicator */}
          <span className="hidden sm:flex items-center gap-1.5 text-[10px] font-semibold text-emerald-400 tracking-widest uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-live" />
            Live
          </span>

          <div className="w-px h-4 bg-border hidden sm:block" />

          <Shield className="w-5 h-5 text-primary flex-shrink-0" />
          <h1 className="text-sm font-bold text-foreground tracking-tight whitespace-nowrap">
            Attack Path Analyzer
          </h1>
          <span className="text-[11px] bg-primary/15 text-primary border border-primary/20 px-2 py-0.5 rounded-full font-medium hidden md:inline">
            nokia-telecom-cluster
          </span>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={reload}
            disabled={graphLoading}
            className="flex items-center gap-1.5 bg-secondary hover:bg-surface-hover text-foreground px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${graphLoading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Reload Graph</span>
          </button>
          <button
            onClick={() => navigate('/demo')}
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-primary-foreground px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity"
          >
            <Play className="w-3.5 h-3.5" />
            Run Demo
          </button>
        </div>
      </header>

      {/* ── Metrics Bar ────────────────────────────────────────── */}
      <div className="flex-shrink-0 flex gap-2 px-3 sm:px-6 py-2 border-b border-border/60 overflow-x-auto scrollbar-thin">
        {/* Threat Score — compact */}
        <div className="w-40 flex-shrink-0">
          <ThreatScoreCard threatScore={analysis.threatScore} loading={graphLoading} />
        </div>

        {/* Stat cards — single row, flex layout */}
        <div className="flex-1 flex gap-2 min-w-0">
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
                <span className="text-[10px] text-muted-foreground">
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
                  {t.label}
                  {activeTab === t.key && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full" />
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
            </div>
          </div>

          {/* CVE Threat Intelligence panel — hidden on md/sm, visible on lg */}
          <div className="hidden lg:flex flex-1 min-h-0 overflow-hidden rounded-xl border border-border bg-card">
            <LiveCveFeedPanel />
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
