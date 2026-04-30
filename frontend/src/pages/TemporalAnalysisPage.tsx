import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Camera, GitCompare, Bell, TrendingUp, RefreshCw } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import SnapshotTimeline from '@/components/SnapshotTimeline';
import SnapshotComparison from '@/components/SnapshotComparison';
import TemporalAlertsPanel from '@/components/TemporalAlertsPanel';
import { useSnapshots, useSnapshotDiff, useSnapshotTimeline } from '@/hooks/useSnapshots';
import type { GraphSnapshot } from '@/api/snapshotApi';
import client from '@/api/client';

type Tab = 'timeline' | 'compare' | 'alerts';

export default function TemporalAnalysisPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('timeline');
  const [snapshotDesc, setSnapshotDesc] = useState('');
  const [selectedBefore, setSelectedBefore] = useState<string>('');
  const [selectedAfter,  setSelectedAfter]  = useState<string>('');
  const [takeMsg, setTakeMsg] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMsg, setDemoMsg] = useState<string | null>(null);

  const { snapshots, total, loading: snapsLoading, error: snapsError, load: loadSnaps, takeSnapshot } = useSnapshots();
  const { diff, loading: diffLoading, error: diffError, compare } = useSnapshotDiff();
  const { timeline, loading: timelineLoading, load: loadTimeline } = useSnapshotTimeline();

  // Auto-run demo on first load
  useEffect(() => {
    const runDemoOnce = async () => {
      loadSnaps();
      loadTimeline(7);

      // Auto-run demo if no snapshots exist
      setTimeout(async () => {
        const res = await client.get('/api/snapshots?limit=1');
        if (res.data.total === 0) {
          // No snapshots yet, run demo automatically
          setDemoMsg('Starting automatic demo...');
          try {
            const demoRes = await client.post('/api/monitor/demo-flow');
            setDemoMsg(`Demo complete! Risk Δ: ${demoRes.data.risk_delta.toFixed(1)}`);
            setTimeout(() => {
              loadSnaps();
              loadTimeline(7);
              setTab('compare');
            }, 1000);
          } catch (e: any) {
            setDemoMsg(`Demo failed: ${e.message}`);
          }
        }
      }, 500);
    };

    runDemoOnce();
  }, []);

  const handleTakeSnapshot = async () => {
    const desc = snapshotDesc.trim() || 'Manual snapshot';
    const result = await takeSnapshot(desc);
    if (result) {
      setSnapshotDesc('');
      setTakeMsg(`Snapshot created: ${result.snapshot_id.slice(0, 8)}…`);
      loadTimeline(7);
      setTimeout(() => setTakeMsg(null), 4000);
    }
  };

  const handleCompare = async () => {
    if (!selectedBefore || !selectedAfter) return;
    await compare(selectedBefore, selectedAfter);
  };

  const autoSelectLatestTwo = () => {
    if (snapshots.length >= 2) {
      setSelectedBefore(snapshots[1].snapshot_id);
      setSelectedAfter(snapshots[0].snapshot_id);
    }
  };

  const handleDemoFlow = async () => {
    setDemoLoading(true);
    setDemoMsg(null);
    try {
      const res = await client.post('/api/monitor/demo-flow');
      setDemoMsg(`✅ Demo Complete!\n• Risk Δ: ${res.data.risk_delta.toFixed(1)}\n• Severity: ${res.data.severity}\n\nRefreshing snapshots...`);

      // Refresh snapshots and timeline
      setTimeout(() => {
        loadSnaps();
        loadTimeline(7);
        setTab('compare');
        // Auto-select latest two for comparison
        setTimeout(() => {
          if (snapshots.length >= 2) {
            setSelectedBefore(snapshots[1]?.snapshot_id || '');
            setSelectedAfter(snapshots[0]?.snapshot_id || '');
          }
        }, 500);
      }, 1000);
    } catch (e: any) {
      setDemoMsg(`❌ Demo failed: ${e.message}`);
    } finally {
      setDemoLoading(false);
    }
  };

  const TABS: { key: Tab; label: string; Icon: any }[] = [
    { key: 'timeline', label: 'Risk Timeline', Icon: TrendingUp },
    { key: 'compare',  label: 'Compare',       Icon: GitCompare },
    { key: 'alerts',   label: 'Alerts',        Icon: Bell },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center gap-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Dashboard
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-semibold">Temporal Analysis</h1>
          <p className="text-xs text-muted-foreground">
            Track graph changes and detect new attack paths over time
          </p>
        </div>
        <ThemeToggle />
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {/* Auto-running demo status */}
        {demoMsg && (
          <div className="bg-gradient-to-r from-purple-500/10 via-blue-500/10 to-cyan-500/10 border border-purple-500/30 rounded-xl p-4">
            <p className="text-sm text-muted-foreground">{demoMsg}</p>
          </div>
        )}

        {/* Snapshot actions */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-3">
            <Camera className="w-4 h-4 text-muted-foreground" />
            <h2 className="font-medium text-sm text-foreground">Create Snapshot</h2>
            <span className="text-xs text-muted-foreground ml-auto">{total} snapshot{total !== 1 ? 's' : ''} stored</span>
          </div>
          <div className="flex gap-3">
            <input
              className="flex-1 bg-secondary/40 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Description (e.g. 'Post-deployment check')"
              value={snapshotDesc}
              onChange={(e) => setSnapshotDesc(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleTakeSnapshot()}
            />
            <button
              onClick={handleTakeSnapshot}
              disabled={snapsLoading}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {snapsLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
              Snapshot
            </button>
          </div>
          {takeMsg && (
            <p className="text-xs text-green-400 mt-2">{takeMsg}</p>
          )}
          {snapsError && (
            <p className="text-xs text-red-400 mt-2">{snapsError}</p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-secondary/30 rounded-lg p-1 w-fit">
          {TABS.map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm transition-colors ${
                tab === key
                  ? 'bg-card text-foreground shadow-sm font-medium'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-card border border-border rounded-xl p-5">
          {/* Timeline tab */}
          {tab === 'timeline' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-medium text-foreground">Risk Over Time (Last 7 Days)</h2>
                <button
                  onClick={() => loadTimeline(7)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  Refresh
                </button>
              </div>
              <SnapshotTimeline timeline={timeline} loading={timelineLoading} />

              {/* Snapshot list */}
              <div className="mt-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Recent Snapshots
                </h3>
                {snapshots.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No snapshots yet.</p>
                ) : (
                  <div className="space-y-1.5 max-h-64 overflow-y-auto">
                    {snapshots.map((s) => (
                      <SnapshotRow key={s.snapshot_id} snapshot={s} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Compare tab */}
          {tab === 'compare' && (
            <div className="space-y-4">
              <h2 className="font-medium text-foreground">Compare Two Snapshots</h2>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Before</label>
                  <select
                    className="w-full bg-secondary/40 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none"
                    value={selectedBefore}
                    onChange={(e) => setSelectedBefore(e.target.value)}
                  >
                    <option value="">— select snapshot —</option>
                    {snapshots.map((s) => (
                      <option key={s.snapshot_id} value={s.snapshot_id}>
                        {new Date(s.timestamp).toLocaleString()} · risk={s.metadata.aggregate_risk.toFixed(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">After</label>
                  <select
                    className="w-full bg-secondary/40 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none"
                    value={selectedAfter}
                    onChange={(e) => setSelectedAfter(e.target.value)}
                  >
                    <option value="">— select snapshot —</option>
                    {snapshots.map((s) => (
                      <option key={s.snapshot_id} value={s.snapshot_id}>
                        {new Date(s.timestamp).toLocaleString()} · risk={s.metadata.aggregate_risk.toFixed(1)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleCompare}
                  disabled={!selectedBefore || !selectedAfter || diffLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {diffLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <GitCompare className="w-4 h-4" />}
                  Compare
                </button>
                {snapshots.length >= 2 && (
                  <button
                    onClick={autoSelectLatestTwo}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors px-3 py-2 border border-border rounded-lg"
                  >
                    Use latest two
                  </button>
                )}
              </div>

              {diffError && <p className="text-xs text-red-400">{diffError}</p>}
              <SnapshotComparison diff={diff} loading={diffLoading} />
            </div>
          )}

          {/* Alerts tab */}
          {tab === 'alerts' && (
            <div className="space-y-4">
              <h2 className="font-medium text-foreground">Temporal Alerts</h2>
              <TemporalAlertsPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SnapshotRow({ snapshot }: { snapshot: GraphSnapshot }) {
  const risk = snapshot.metadata.aggregate_risk;
  const riskColor = risk >= 7 ? '#E24B4A' : risk >= 4 ? '#EF9F27' : '#1D9E75';
  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-secondary/20 rounded-lg text-xs">
      <span className="font-mono text-muted-foreground">{snapshot.snapshot_id.slice(0, 8)}…</span>
      <span className="text-muted-foreground flex-1 truncate">
        {new Date(snapshot.timestamp).toLocaleString()}
      </span>
      <span className="text-muted-foreground">{snapshot.metadata.node_count}n</span>
      <span className="font-semibold" style={{ color: riskColor }}>
        {risk.toFixed(1)}
      </span>
      <span className="text-muted-foreground capitalize">{snapshot.trigger.source}</span>
    </div>
  );
}
