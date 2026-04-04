import { ArrowUp, ArrowDown, Minus, AlertTriangle, GitCompare } from 'lucide-react';
import type { SnapshotDiff } from '@/api/snapshotApi';

interface Props {
  diff: SnapshotDiff | null;
  loading?: boolean;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#E24B4A',
  high: '#EF9F27',
  medium: '#378ADD',
  low: '#1D9E75',
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className="text-xs font-semibold uppercase px-2 py-0.5 rounded"
      style={{
        backgroundColor: `${SEVERITY_COLORS[severity] ?? '#888780'}22`,
        color: SEVERITY_COLORS[severity] ?? '#888780',
      }}
    >
      {severity}
    </span>
  );
}

function Delta({ value, label }: { value: number; label: string }) {
  const color = value > 0 ? '#E24B4A' : value < 0 ? '#1D9E75' : '#888780';
  const Icon = value > 0 ? ArrowUp : value < 0 ? ArrowDown : Minus;
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-center gap-1" style={{ color }}>
        <Icon className="w-3 h-3" />
        <span className="text-lg font-bold">{Math.abs(value)}</span>
      </div>
      <span className="text-[10px] text-muted-foreground text-center">{label}</span>
    </div>
  );
}

export default function SnapshotComparison({ diff, loading }: Props) {
  if (loading) {
    return (
      <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
        Computing diff…
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 h-40 text-muted-foreground">
        <GitCompare className="w-8 h-8 opacity-40" />
        <p className="text-sm">Select two snapshots to compare</p>
      </div>
    );
  }

  const ts = (s: string) => {
    try { return new Date(s).toLocaleString(); } catch { return s; }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground space-y-0.5">
          <p><span className="font-medium text-foreground">Before:</span> {ts(diff.timestamp_before)}</p>
          <p><span className="font-medium text-foreground">After:</span>  {ts(diff.timestamp_after)}</p>
        </div>
        <div className="flex items-center gap-2">
          <SeverityBadge severity={diff.severity} />
          {diff.alert_triggered && (
            <AlertTriangle className="w-4 h-4 text-orange-400" title="Alert was triggered" />
          )}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-4 gap-2 bg-secondary/20 rounded-lg p-3">
        <Delta value={diff.nodes_added_count - diff.nodes_removed_count} label="Nodes Δ" />
        <Delta value={diff.edges_added_count - diff.edges_removed_count} label="Edges Δ" />
        <Delta value={diff.new_attack_paths_count} label="New Paths" />
        <Delta value={diff.new_cycles_count} label="New Cycles" />
      </div>

      {/* Risk delta */}
      <div className="flex items-center justify-between bg-secondary/20 rounded-lg px-3 py-2">
        <span className="text-xs text-muted-foreground">Aggregate Risk Δ</span>
        <span
          className="text-sm font-bold"
          style={{ color: diff.overall_risk_delta > 0 ? '#E24B4A' : diff.overall_risk_delta < 0 ? '#1D9E75' : '#888' }}
        >
          {diff.overall_risk_delta > 0 ? '+' : ''}{diff.overall_risk_delta.toFixed(2)}
        </span>
      </div>

      {/* Alert reasons */}
      {diff.alert_reasons.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Alert Reasons
          </p>
          {diff.alert_reasons.map((r, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-foreground">
              <span className="mt-0.5 text-orange-400">•</span>
              {r}
            </div>
          ))}
        </div>
      )}

      {/* New attack paths */}
      {diff.new_attack_paths.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold text-red-400 uppercase tracking-wide">
            New Attack Paths
          </p>
          {diff.new_attack_paths.map((p, i) => (
            <div key={i} className="text-xs font-mono text-muted-foreground bg-red-500/10 rounded px-2 py-1">
              {p.source} → {p.target}
            </div>
          ))}
        </div>
      )}

      {/* New cycles */}
      {diff.new_cycles.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold text-orange-400 uppercase tracking-wide">
            New Cycles
          </p>
          {diff.new_cycles.map((c, i) => (
            <div key={i} className="text-xs font-mono text-muted-foreground bg-orange-500/10 rounded px-2 py-1">
              {c.nodes.join(' → ')}
            </div>
          ))}
        </div>
      )}

      {/* Nodes added / removed */}
      {(diff.nodes_added.length > 0 || diff.nodes_removed.length > 0) && (
        <div className="grid grid-cols-2 gap-2">
          {diff.nodes_added.length > 0 && (
            <div>
              <p className="text-[10px] text-green-400 font-semibold uppercase mb-1">Added Nodes</p>
              {diff.nodes_added.slice(0, 5).map((n) => (
                <p key={n} className="text-[10px] font-mono text-muted-foreground truncate">{n}</p>
              ))}
              {diff.nodes_added.length > 5 && (
                <p className="text-[10px] text-muted-foreground">+{diff.nodes_added.length - 5} more</p>
              )}
            </div>
          )}
          {diff.nodes_removed.length > 0 && (
            <div>
              <p className="text-[10px] text-red-400 font-semibold uppercase mb-1">Removed Nodes</p>
              {diff.nodes_removed.slice(0, 5).map((n) => (
                <p key={n} className="text-[10px] font-mono text-muted-foreground truncate line-through">{n}</p>
              ))}
              {diff.nodes_removed.length > 5 && (
                <p className="text-[10px] text-muted-foreground">+{diff.nodes_removed.length - 5} more</p>
              )}
            </div>
          )}
        </div>
      )}

      {diff.nodes_added_count === 0 && diff.nodes_removed_count === 0 &&
       diff.new_attack_paths_count === 0 && diff.new_cycles_count === 0 && (
        <p className="text-sm text-muted-foreground text-center py-2">
          No significant changes detected between these snapshots.
        </p>
      )}
    </div>
  );
}
