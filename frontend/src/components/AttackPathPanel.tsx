import { useState } from 'react';
import { Loader2, Play, Zap, ArrowRight } from 'lucide-react';
import SeverityBadge from './SeverityBadge';
import type { GraphNode } from '@/hooks/useGraph';

interface Props {
  nodes: GraphNode[];
  attackPath: any;
  loading: boolean;
  onFindPath: (source: string, target: string) => void;
  onAutoDetect: () => void;
  onShowOnGraph: () => void;
}

const FALLBACK_SOURCES = [
  'pod:default:web-server', 'pod:default:api-server',
  'user:cluster:dev-1', 'user:cluster:ci-bot',
];
const FALLBACK_TARGETS = [
  'database:default:billing-db', 'secret:default:db-credentials',
];

export default function AttackPathPanel({ nodes, attackPath, loading, onFindPath, onAutoDetect, onShowOnGraph }: Props) {
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');

  const sources = nodes.filter(n => ['pod', 'user', 'service_account'].includes(n.type));
  const targets = nodes.filter(n => ['database', 'secret'].includes(n.type));

  const sourceList = sources.length > 0
    ? sources
    : nodes.length > 0
      ? nodes
      : FALLBACK_SOURCES.map(id => ({ id, label: id.split(':').pop()!, type: id.split(':')[0] } as GraphNode));

  const targetList = targets.length > 0
    ? targets
    : nodes.length > 0
      ? [...nodes].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
      : FALLBACK_TARGETS.map(id => ({ id, label: id.split(':').pop()!, type: id.split(':')[0] } as GraphNode));

  return (
    <div className="space-y-4 p-4">
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Source Node</label>
        <select value={source} onChange={e => setSource(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select source...</option>
          {sourceList.map(n => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Target Node</label>
        <select value={target} onChange={e => setTarget(e.target.value)} className="w-full bg-secondary text-foreground rounded-md px-3 py-2 text-sm border border-border">
          <option value="">Select target...</option>
          {targetList.map(n => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
        </select>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => source && target && onFindPath(source, target)}
          disabled={!source || !target || loading}
          className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Find Path
        </button>
        <button
          onClick={onAutoDetect}
          disabled={loading}
          className="flex items-center gap-2 bg-secondary text-foreground rounded-md px-3 py-2 text-sm font-medium hover:bg-surface-hover transition-colors"
        >
          <Zap className="w-4 h-4" />
          Auto Detect
        </button>
      </div>

      {/* Results */}
      {attackPath && (
        <div className="space-y-3 mt-4">
          {attackPath.path && attackPath.path.length > 0 ? (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">Kill Chain ({attackPath.path.length} hops)</span>
                {attackPath.total_cost != null && (
                  <span className="text-xs text-muted-foreground">Cost: {attackPath.total_cost.toFixed(1)}</span>
                )}
              </div>
              <div className="space-y-2">
                {attackPath.path.map((step: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 p-2 bg-secondary rounded text-sm">
                    <span className="text-foreground font-medium">{step.from_label || step.from}</span>
                    <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                    <span className="text-xs text-muted-foreground">[{step.relation}]</span>
                    <ArrowRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                    <span className="text-foreground font-medium">{step.to_label || step.to}</span>
                    {step.severity && <SeverityBadge severity={step.severity} />}
                    {step.risk_score != null && (
                      <span className="text-xs text-muted-foreground ml-auto">{step.risk_score}</span>
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={onShowOnGraph}
                className="w-full bg-destructive/20 text-destructive border border-destructive/30 rounded-md px-3 py-2 text-sm font-medium hover:bg-destructive/30 transition-colors"
              >
                Show on Graph
              </button>
            </>
          ) : (
            <div className="text-center py-6 text-destructive">
              <p className="font-medium">No attack path found</p>
              <p className="text-xs text-muted-foreground mt-1">Try different source/target nodes</p>
            </div>
          )}
        </div>
      )}

      {!attackPath && !loading && (
        <div className="text-center py-8 text-muted-foreground">
          <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Run analysis to find attack paths</p>
        </div>
      )}
    </div>
  );
}
