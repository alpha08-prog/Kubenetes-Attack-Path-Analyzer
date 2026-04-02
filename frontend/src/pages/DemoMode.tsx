import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Pause, Play, RotateCcw, Loader2, CheckCircle, AlertTriangle, Shield, Download } from 'lucide-react';
import * as api from '@/api/graphApi';
import SeverityBadge from '@/components/SeverityBadge';
import FindingCard from '@/components/FindingCard';
import { NODE_COLORS } from '@/styles/nodeColors';

const STEPS = [
  'Loading cluster data...',
  'Detecting attack paths...',
  'Analyzing blast radius...',
  'Detecting privilege escalation loops...',
  'Identifying critical nodes...',
  'Generating AI security report...',
];

function normalizeAttackPath(raw: any) {
  if (!raw) return raw;
  if (Array.isArray(raw.path) && raw.path.length > 0 && typeof raw.path[0] === 'string' && Array.isArray(raw.hops)) {
    if (raw.hops.length === 0) {
      return {
        ...raw,
        path: [],
        message: raw.message || 'Source and target resolved to the same node.',
      };
    }

    return {
      ...raw,
      path: raw.hops.map((hop: any) => ({
        from: hop.from,
        to: hop.to,
        from_label: hop.from_label,
        to_label: hop.to_label,
        relation: hop.relation,
      })),
    };
  }
  return raw;
}

function normalizeBlastRadius(raw: any) {
  if (!raw) return raw;
  return {
    ...raw,
    total_affected: raw.total_affected ?? raw.total_reachable ?? 0,
  };
}

function normalizeSummary(rawSummary: any, rawGraph: any) {
  const nodes = rawGraph?.nodes || [];
  const criticalCount = nodes.filter((node: any) => {
    const data = node?.data ?? node ?? {};
    return Number(data.risk_score ?? data.risk ?? 0) >= 8;
  }).length;

  return {
    total_nodes: Number(rawSummary?.total_nodes ?? nodes.length ?? 0),
    total_edges: Number(rawSummary?.total_edges ?? (rawGraph?.edges || []).length ?? 0),
    critical_findings: Number(rawSummary?.critical_findings ?? criticalCount),
    cycles_detected: Number(rawSummary?.cycles_detected ?? rawSummary?.cycle_count ?? 0),
  };
}

function formatCycleChain(cycle: any): string {
  if (typeof cycle?.chain_string === 'string' && cycle.chain_string.length > 0) {
    return cycle.chain_string;
  }
  if (typeof cycle?.chain === 'string' && cycle.chain.length > 0) {
    return cycle.chain;
  }
  if (Array.isArray(cycle?.chain)) {
    return cycle.chain.join(' -> ');
  }
  if (Array.isArray(cycle?.nodes)) {
    return cycle.nodes.join(' -> ');
  }
  return '';
}

export default function DemoMode() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [paused, setPaused] = useState(false);
  const [stepData, setStepData] = useState<Record<number, any>>({});
  const [stepDone, setStepDone] = useState<Set<number>>(new Set());
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const timerRef = useRef<any>(null);

  const runStep = useCallback(async (step: number) => {
    try {
      let data: any = null;
      switch (step) {
        case 0:
          const [g, s] = await Promise.all([api.getGraph(), api.getGraphSummary()]);
          data = { graph: g.data, summary: normalizeSummary(s.data, g.data) };
          break;
        case 1:
          data = normalizeAttackPath((await api.getAutoAttackPath()).data);
          break;
        case 2:
          const src = stepData[1]?.path?.[0]?.from || 'pod:default:web-server';
          data = normalizeBlastRadius((await api.getBlastRadius(src, 3)).data);
          break;
        case 3:
          data = (await api.getCycles()).data;
          break;
        case 4:
          data = (await api.getCriticalNodes(5)).data;
          break;
        case 5:
          data = (await api.getReport()).data;
          break;
      }
      setStepData(prev => ({ ...prev, [step]: data }));
      setStepDone(prev => new Set(prev).add(step));
    } catch {
      setStepDone(prev => new Set(prev).add(step));
    }
  }, [stepData]);

  useEffect(() => {
    if (paused) return;
    runStep(currentStep);
  }, [currentStep, paused]);

  useEffect(() => {
    if (paused || !stepDone.has(currentStep) || currentStep >= STEPS.length - 1) return;
    timerRef.current = setTimeout(() => setCurrentStep(p => p + 1), 2500);
    return () => clearTimeout(timerRef.current);
  }, [stepDone, currentStep, paused]);

  const restart = () => {
    setCurrentStep(0);
    setStepData({});
    setStepDone(new Set());
    setPaused(false);
  };

  const downloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const response = await api.getReportPdf();
      const contentDisposition = response.headers['content-disposition'] as string | undefined;
      const fileNameMatch = contentDisposition?.match(/filename="?([^"]+)"?/i);
      const fileName = fileNameMatch?.[1] || 'security-report.pdf';
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const summary = stepData[0]?.summary;
  const attackPath = stepData[1];
  const blastRadius = stepData[2];
  const cycles = stepData[3];
  const criticalNodes = stepData[4];
  const report = stepData[5];

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-bold">Attack Path Analyzer — Demo</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setPaused(!paused)} className="flex items-center gap-2 bg-secondary text-foreground px-3 py-1.5 rounded-md text-sm">
            {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button onClick={restart} className="flex items-center gap-2 bg-secondary text-foreground px-3 py-1.5 rounded-md text-sm">
            <RotateCcw className="w-4 h-4" />
            Restart
          </button>
          <button onClick={() => navigate('/')} className="flex items-center gap-2 bg-secondary text-foreground px-3 py-1.5 rounded-md text-sm">
            <ArrowLeft className="w-4 h-4" />
            Dashboard
          </button>
        </div>
      </div>

      {/* Progress */}
      <div className="flex items-center justify-center gap-2 py-4">
        {STEPS.map((_, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              stepDone.has(i) ? 'bg-accent text-accent-foreground' :
              i === currentStep ? 'bg-primary text-primary-foreground animate-pulse' :
              'bg-secondary text-muted-foreground'
            }`}>
              {stepDone.has(i) ? <CheckCircle className="w-4 h-4" /> : i + 1}
            </div>
            {i < STEPS.length - 1 && <div className={`w-8 h-0.5 ${stepDone.has(i) ? 'bg-accent' : 'bg-secondary'}`} />}
          </div>
        ))}
      </div>

      <p className="text-center text-lg font-medium mb-6">
        Step {currentStep + 1}/6: {STEPS[currentStep]}
        {!stepDone.has(currentStep) && <Loader2 className="w-5 h-5 inline ml-2 animate-spin" />}
      </p>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-6 space-y-6 pb-12">
        {/* Step 0 - Cluster */}
        {stepDone.has(0) && summary && (
          <div className="animate-slide-in-right bg-card border border-border rounded-lg p-6">
            <h3 className="font-semibold mb-3">Cluster Overview</h3>
            <div className="grid grid-cols-4 gap-3">
              <div className="text-center"><p className="text-2xl font-bold text-primary">{summary.total_nodes}</p><p className="text-xs text-muted-foreground">Nodes</p></div>
              <div className="text-center"><p className="text-2xl font-bold text-accent">{summary.total_edges}</p><p className="text-xs text-muted-foreground">Edges</p></div>
              <div className="text-center"><p className="text-2xl font-bold text-destructive">{summary.critical_findings}</p><p className="text-xs text-muted-foreground">Critical</p></div>
              <div className="text-center"><p className="text-2xl font-bold text-node-role">{summary.cycles_detected}</p><p className="text-xs text-muted-foreground">Cycles</p></div>
            </div>
          </div>
        )}

        {/* Step 1 - Attack path */}
        {stepDone.has(1) && Array.isArray(attackPath?.path) && attackPath.path.length > 0 && (
          <div className="animate-slide-in-right bg-card border border-border rounded-lg p-6">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-destructive" />
              Attack Path Detected
            </h3>
            <pre className="text-sm font-mono bg-background rounded p-3 text-destructive overflow-x-auto">
              {attackPath.path.map((s: any) => `${s.from_label || s.from} →[${s.relation}]→ ${s.to_label || s.to}`).join('\n')}
            </pre>
          </div>
        )}

        {/* Step 2 - Blast */}
        {stepDone.has(2) && blastRadius && (
          <div className="animate-slide-in-right bg-card border border-border rounded-lg p-6">
            <h3 className="font-semibold mb-3">Blast Radius Analysis</h3>
            <p className="text-2xl font-bold text-severity-high">{blastRadius.total_affected ?? 0} nodes at risk</p>
          </div>
        )}

        {/* Step 3 - Cycles */}
        {stepDone.has(3) && (
          <div className="animate-slide-in-right bg-card border border-border rounded-lg p-6">
            <h3 className="font-semibold mb-3">Privilege Escalation Cycles</h3>
            {(cycles?.cycles || []).length > 0 ? (
              (cycles.cycles).map((c: any, i: number) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-severity-high" />
                  <span className="text-sm font-mono">{formatCycleChain(c)}</span>
                </div>
              ))
            ) : (
              <p className="text-severity-low">No cycles detected ✓</p>
            )}
          </div>
        )}

        {/* Step 4 - Critical */}
        {stepDone.has(4) && (
          <div className="animate-slide-in-right bg-card border border-border rounded-lg p-6">
            <h3 className="font-semibold mb-3">Top Critical Nodes</h3>
            {(criticalNodes?.nodes || criticalNodes || []).slice(0, 3).map((n: any, i: number) => (
              <div key={i} className="flex items-center gap-3 mb-2">
                <span className="text-lg font-bold text-muted-foreground">#{i + 1}</span>
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: NODE_COLORS[n.type] || '#8b8fa8' }} />
                <span className="font-medium">{n.label || n.id}</span>
                <SeverityBadge severity={n.risk_score >= 8 ? 'critical' : n.risk_score >= 6 ? 'high' : 'medium'} />
              </div>
            ))}
          </div>
        )}

        {/* Step 5 - Report */}
        {stepDone.has(5) && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-lg">AI Security Report</h3>
              <button
                onClick={downloadPdf}
                disabled={downloadingPdf}
                className="flex items-center gap-2 bg-secondary text-foreground px-3 py-1.5 rounded-md text-sm hover:bg-surface-hover transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              >
                {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Download PDF
              </button>
            </div>
            {(report?.findings || report || []).map((f: any, i: number) => (
              <div key={i} className="animate-slide-in-right" style={{ animationDelay: `${i * 150}ms` }}>
                <FindingCard finding={f} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
