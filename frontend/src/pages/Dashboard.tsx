import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, RefreshCw, Play, Network, GitBranch, AlertTriangle, RotateCcw } from 'lucide-react';
import { useGraph } from '@/hooks/useGraph';
import { useAnalysis } from '@/hooks/useAnalysis';
import GraphCanvas from '@/components/GraphCanvas';
import StatCard from '@/components/StatCard';
import AttackPathPanel from '@/components/AttackPathPanel';
import BlastRadiusPanel from '@/components/BlastRadiusPanel';
import CyclesPanel from '@/components/CyclesPanel';
import CriticalNodeTable from '@/components/CriticalNodeTable';
import SimulationPanel from '@/components/SimulationPanel';
import SimulationModal from '@/components/SimulationModal';
import NarratorPanel from '@/components/NarratorPanel';

type OverlayMode = 'default' | 'attack' | 'blast' | 'cycle';
type Tab = 'attack' | 'blast' | 'cycles' | 'simulation';

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
    await analysis.runSimulation(nodeId, src, tgt);
    setSimModal(analysis.simulation);
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'attack', label: 'Attack Path' },
    { key: 'blast', label: 'Blast Radius' },
    { key: 'cycles', label: 'Cycles & Critical' },
    { key: 'simulation', label: 'Simulation' },
  ];

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-card">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-bold text-foreground">Attack Path Analyzer</h1>
          <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded font-medium">
            nokia-telecom-cluster
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={reload}
            disabled={graphLoading}
            className="flex items-center gap-2 bg-secondary text-foreground px-3 py-1.5 rounded-md text-sm hover:bg-surface-hover transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${graphLoading ? 'animate-spin' : ''}`} />
            Reload Graph
          </button>
          <button
            onClick={() => navigate('/demo')}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-3 py-1.5 rounded-md text-sm hover:opacity-90 transition-opacity"
          >
            <Play className="w-4 h-4" />
            Run Demo
          </button>
        </div>
      </header>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 px-6 py-3">
        <StatCard title="Total Nodes" value={summary?.total_nodes ?? '—'} icon={<Network className="w-4 h-4" />} color="#378ADD" loading={graphLoading} />
        <StatCard title="Total Edges" value={summary?.total_edges ?? '—'} icon={<GitBranch className="w-4 h-4" />} color="#1D9E75" loading={graphLoading} />
        <StatCard title="Critical Findings" value={summary?.critical_findings ?? '—'} icon={<AlertTriangle className="w-4 h-4" />} color="#E24B4A" loading={graphLoading} />
        <StatCard title="Cycles Detected" value={summary?.cycles_detected ?? '—'} icon={<RotateCcw className="w-4 h-4" />} color="#7F77DD" loading={graphLoading} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0 px-6 pb-0 gap-4">
        {/* Left - Graph */}
        <div className="w-[60%] flex flex-col min-h-0">
          {/* Overlay toggles */}
          <div className="flex gap-2 mb-2">
            {[
              { mode: 'default' as OverlayMode, label: 'Default' },
              { mode: 'attack' as OverlayMode, label: 'Attack Path' },
              { mode: 'blast' as OverlayMode, label: 'Blast Radius' },
              { mode: 'cycle' as OverlayMode, label: 'Cycles' },
            ].map(m => (
              <button
                key={m.mode}
                onClick={() => setOverlayMode(m.mode)}
                className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
                  overlayMode === m.mode
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-muted-foreground hover:text-foreground'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
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

        {/* Right - Tabs */}
        <div className="w-[40%] flex flex-col min-h-0 bg-card border border-border rounded-lg overflow-hidden">
          <div className="flex border-b border-border">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`flex-1 text-xs py-2.5 font-medium transition-colors ${
                  activeTab === t.key
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
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
      </div>

      {/* Bottom - Narrator */}
      <NarratorPanel
        report={analysis.report}
        loading={analysis.loading.report}
        onFetchReport={analysis.fetchReport}
      />

      {/* Simulation Modal */}
      {simModal && (
        <SimulationModal
          simulation={simModal}
          onClose={() => setSimModal(null)}
        />
      )}
    </div>
  );
}
