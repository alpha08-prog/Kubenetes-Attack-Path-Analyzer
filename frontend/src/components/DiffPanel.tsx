import { useState, useEffect } from 'react';
import { GitCompare, Loader2, TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle } from 'lucide-react';
import { getDiffLatest, compareDiffRuns, getDiffVsCurrent, getRunHistory } from '@/api/graphApi';
import { cn } from '@/lib/utils';

type DiffMode = 'latest' | 'compare' | 'vs-current';

function DeltaBadge({ delta, suffix = '' }: { delta: number; suffix?: string }) {
  if (delta > 0) return (
    <span className="inline-flex items-center gap-0.5 text-red-400 font-semibold text-xs">
      <TrendingUp className="w-3 h-3" />+{delta}{suffix}
    </span>
  );
  if (delta < 0) return (
    <span className="inline-flex items-center gap-0.5 text-emerald-400 font-semibold text-xs">
      <TrendingDown className="w-3 h-3" />{delta}{suffix}
    </span>
  );
  return (
    <span className="inline-flex items-center gap-0.5 text-muted-foreground text-xs">
      <Minus className="w-3 h-3" />0{suffix}
    </span>
  );
}

function MetricRow({ label, before, after, delta, suffix = '' }: {
  label: string; before: number; after: number; delta: number; suffix?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">{before}{suffix}</span>
        <span className="text-muted-foreground">→</span>
        <span className="text-foreground font-medium">{after}{suffix}</span>
        <DeltaBadge delta={delta} suffix={suffix} />
      </div>
    </div>
  );
}

export default function DiffPanel() {
  const [mode, setMode] = useState<DiffMode>('latest');
  const [runs, setRuns] = useState<any[]>([]);
  const [beforeId, setBeforeId] = useState('');
  const [afterId, setAfterId] = useState('');
  const [vsRunId, setVsRunId] = useState('');
  const [diff, setDiff] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load run history for dropdowns
  useEffect(() => {
    if (mode === 'compare' || mode === 'vs-current') {
      getRunHistory(20)
        .then(r => setRuns(r.data?.runs || []))
        .catch(() => setRuns([]));
    }
  }, [mode]);

  const runDiff = async () => {
    setLoading(true);
    setError(null);
    setDiff(null);
    try {
      let res;
      if (mode === 'latest') {
        res = await getDiffLatest();
      } else if (mode === 'compare') {
        if (!beforeId || !afterId) { setError('Select both runs to compare.'); setLoading(false); return; }
        res = await compareDiffRuns(beforeId, afterId);
      } else {
        if (!vsRunId) { setError('Select a baseline run.'); setLoading(false); return; }
        res = await getDiffVsCurrent(vsRunId);
      }
      setDiff(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Diff failed. Make sure there are at least 2 recorded runs.');
    } finally {
      setLoading(false);
    }
  };

  const fmtTime = (ts: string) => {
    if (!ts) return '—';
    try { return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return ts; }
  };

  const runLabel = (run: any) =>
    `${fmtTime(run.created_at)} · risk ${run.overall_risk?.toFixed(1) ?? '?'} · ${run.run_id.slice(0, 8)}`;

  return (
    <div className="space-y-4 p-4">
      {/* Mode selector */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground">Compare Mode</label>
        <div className="flex rounded-lg bg-secondary/60 p-0.5 gap-0.5">
          {([
            { key: 'latest',     label: 'Latest 2' },
            { key: 'compare',    label: 'Pick Runs' },
            { key: 'vs-current', label: 'vs Live' },
          ] as { key: DiffMode; label: string }[]).map(m => (
            <button
              key={m.key}
              onClick={() => { setMode(m.key); setDiff(null); setError(null); }}
              className={`flex-1 text-[11px] py-1.5 rounded-md font-medium transition-all ${
                mode === m.key ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Run selectors */}
      {mode === 'compare' && (
        <div className="space-y-2">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Baseline (Before)</label>
            <select value={beforeId} onChange={e => setBeforeId(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-2 py-1.5 text-xs border border-border">
              <option value="">Select run...</option>
              {runs.map(r => <option key={r.run_id} value={r.run_id}>{runLabel(r)}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Comparison (After)</label>
            <select value={afterId} onChange={e => setAfterId(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-2 py-1.5 text-xs border border-border">
              <option value="">Select run...</option>
              {runs.map(r => <option key={r.run_id} value={r.run_id}>{runLabel(r)}</option>)}
            </select>
          </div>
        </div>
      )}

      {mode === 'vs-current' && (
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Baseline Run</label>
          <select value={vsRunId} onChange={e => setVsRunId(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-2 py-1.5 text-xs border border-border">
            <option value="">Select baseline...</option>
            {runs.map(r => <option key={r.run_id} value={r.run_id}>{runLabel(r)}</option>)}
          </select>
          <p className="text-[10px] text-muted-foreground">Compares selected run against the current live graph state.</p>
        </div>
      )}

      {mode === 'latest' && (
        <p className="text-[11px] text-muted-foreground">Automatically diffs the two most recent recorded analysis runs.</p>
      )}

      <button
        onClick={runDiff}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitCompare className="w-4 h-4" />}
        Run Diff
      </button>

      {error && (
        <div className="flex items-start gap-2 bg-destructive/10 border border-destructive/30 rounded-lg p-3">
          <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
          <p className="text-xs text-destructive">{error}</p>
        </div>
      )}

      {diff && (
        <div className="space-y-4">
          {/* Meta */}
          <div className="bg-secondary/40 rounded-lg p-3 text-[11px] text-muted-foreground space-y-0.5">
            <div className="flex justify-between"><span>Before</span><span className="text-foreground">{fmtTime(diff.meta?.time_before)}</span></div>
            <div className="flex justify-between"><span>After</span><span className="text-foreground">{fmtTime(diff.meta?.time_after)}</span></div>
            {diff.meta?.note && <div className="text-primary pt-1">{diff.meta.note}</div>}
          </div>

          {/* Key metrics */}
          <div>
            <p className="text-xs font-semibold text-foreground mb-2">Risk Metrics</p>
            <div className="bg-secondary/20 rounded-lg px-3 py-1">
              <MetricRow
                label="Overall Risk"
                before={diff.risk_delta?.before ?? 0}
                after={diff.risk_delta?.after ?? 0}
                delta={diff.risk_delta?.delta ?? 0}
                suffix=""
              />
              <MetricRow
                label="Attack Paths"
                before={diff.path_delta?.before ?? 0}
                after={diff.path_delta?.after ?? 0}
                delta={diff.path_delta?.delta ?? 0}
              />
              <MetricRow
                label="Priv-Esc Cycles"
                before={diff.cycle_delta?.before ?? 0}
                after={diff.cycle_delta?.after ?? 0}
                delta={diff.cycle_delta?.delta ?? 0}
              />
              <MetricRow
                label="Total Nodes"
                before={diff.node_changes?.total_before ?? 0}
                after={diff.node_changes?.total_after ?? 0}
                delta={(diff.node_changes?.total_after ?? 0) - (diff.node_changes?.total_before ?? 0)}
              />
              <MetricRow
                label="Total Edges"
                before={diff.edge_changes?.total_before ?? 0}
                after={diff.edge_changes?.total_after ?? 0}
                delta={(diff.edge_changes?.total_after ?? 0) - (diff.edge_changes?.total_before ?? 0)}
              />
            </div>
          </div>

          {/* Severity shift */}
          {diff.severity_shift?.deltas && (
            <div>
              <p className="text-xs font-semibold text-foreground mb-2">Severity Shift</p>
              <div className="grid grid-cols-2 gap-1.5">
                {(['critical', 'high', 'medium', 'low'] as const).map(sev => {
                  const before = diff.severity_shift.before[sev] ?? 0;
                  const after = diff.severity_shift.after[sev] ?? 0;
                  const delta = diff.severity_shift.deltas[sev] ?? 0;
                  const colors: Record<string, string> = {
                    critical: 'text-red-400', high: 'text-orange-400',
                    medium: 'text-yellow-400', low: 'text-emerald-400',
                  };
                  return (
                    <div key={sev} className="bg-secondary/30 rounded-lg p-2 text-center">
                      <p className={`text-[10px] font-medium capitalize ${colors[sev]}`}>{sev}</p>
                      <p className="text-base font-bold text-foreground">{after}</p>
                      <DeltaBadge delta={delta} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* New findings */}
          {diff.finding_delta && (diff.finding_delta.new_count > 0 || diff.finding_delta.resolved_count > 0) && (
            <div>
              <p className="text-xs font-semibold text-foreground mb-2">Findings</p>
              <div className="flex gap-2 mb-2">
                {diff.finding_delta.new_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-red-500/10 text-red-400 border border-red-500/20 rounded px-2 py-0.5">
                    <AlertTriangle className="w-3 h-3" />+{diff.finding_delta.new_count} new
                  </span>
                )}
                {diff.finding_delta.resolved_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded px-2 py-0.5">
                    <CheckCircle className="w-3 h-3" />{diff.finding_delta.resolved_count} resolved
                  </span>
                )}
              </div>
              {diff.finding_delta.new_findings?.slice(0, 3).map((f: any, i: number) => (
                <div key={i} className="text-[11px] py-1 border-b border-border/30 last:border-0">
                  <span className={`font-medium ${f.severity === 'critical' ? 'text-red-400' : f.severity === 'high' ? 'text-orange-400' : 'text-foreground'}`}>
                    [{f.severity}]
                  </span>{' '}
                  <span className="text-muted-foreground">{f.title}</span>
                </div>
              ))}
            </div>
          )}

          {/* Top new risks */}
          {diff.top_new_risks?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground mb-2">Top New Risks</p>
              <div className="space-y-1">
                {diff.top_new_risks.map((n: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-1.5">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{n.label}</p>
                      <p className="text-[10px] text-muted-foreground">{n.type}{n.is_new ? ' · new node' : ''}</p>
                    </div>
                    <DeltaBadge delta={n.delta} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top improved */}
          {diff.top_improved?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground mb-2">Most Improved</p>
              <div className="space-y-1">
                {diff.top_improved.map((n: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-emerald-500/5 border border-emerald-500/10 rounded-lg px-3 py-1.5">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{n.label}</p>
                      <p className="text-[10px] text-muted-foreground">{n.type}</p>
                    </div>
                    <DeltaBadge delta={n.delta} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation & Alerts */}
          {diff.recommendation && (
            <div className={cn(
              "rounded-lg p-4 border-l-4",
              diff.recommendation.alert_level === 'critical' ? "bg-red-500/10 border-red-500 text-red-200" :
              diff.recommendation.alert_level === 'high'     ? "bg-orange-500/10 border-orange-500 text-orange-200" :
              diff.recommendation.alert_level === 'success'  ? "bg-emerald-500/10 border-emerald-500 text-emerald-200" :
              "bg-secondary/40 border-primary text-muted-foreground"
            )}>
              <div className="flex items-start gap-3">
                {diff.recommendation.alert_level === 'critical' && <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 animate-pulse" />}
                {diff.recommendation.alert_level === 'high'     && <AlertTriangle className="w-5 h-5 text-orange-500 shrink-0" />}
                {diff.recommendation.alert_level === 'success'  && <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0" />}
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider mb-1">
                    {diff.recommendation.alert_level === 'critical' ? 'Security Alert: Critical Regression' : 
                     diff.recommendation.alert_level === 'high'     ? 'Security Warning' : 
                     diff.recommendation.alert_level === 'success'  ? 'Security Improvement' : 'Analysis Summary'}
                  </p>
                  <p className="text-xs leading-relaxed italic opacity-90">
                    {typeof diff.recommendation === 'string' ? diff.recommendation : diff.recommendation.text}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Top New Edges */}
          {diff.edge_changes?.new_edges?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground mb-2">New Connections (Edges)</p>
              <div className="space-y-1">
                {diff.edge_changes.new_edges.map((e: any, i: number) => (
                  <div key={i} className="bg-secondary/20 rounded-lg px-3 py-2 text-[10px] space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground font-mono truncate max-w-[100px]">{e.source.split(':').pop()}</span>
                      <span className="text-primary font-bold">-{e.relation}→</span>
                      <span className="text-muted-foreground font-mono truncate max-w-[100px]">{e.target.split(':').pop()}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!diff && !loading && !error && (
        <div className="text-center py-8 text-muted-foreground">
          <GitCompare className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">Compare two analysis runs to see what changed</p>
          <p className="text-xs mt-1 opacity-60">Use POST /api/history/record to create snapshots</p>
        </div>
      )}
    </div>
  );
}
