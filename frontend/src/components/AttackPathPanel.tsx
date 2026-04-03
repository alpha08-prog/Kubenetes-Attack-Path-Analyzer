import { useState } from 'react';
import { Loader2, Play, Zap, ArrowRight, Copy, CheckCircle2 } from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'path' | 'remediation'>('path');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

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
    <div className="space-y-3 p-3">
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

      {/* Loading state */}
      {loading && (
        <div className="p-6 flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">Analyzing paths...</p>
            <p className="text-xs text-muted-foreground mt-1">This may take a few seconds</p>
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && attackPath && (
        <div className="space-y-3 mt-4">
          {attackPath.path && attackPath.path.length > 0 ? (
            <>
              {/* Tabs */}
              <div className="flex border-b border-border">
                <button
                  onClick={() => setActiveTab('path')}
                  className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'path'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Kill Chain
                </button>
                <button
                  onClick={() => setActiveTab('remediation')}
                  className={`flex-1 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'remediation'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Remediation ({attackPath.remediations?.length || 0})
                </button>
              </div>

              {/* Kill Chain Tab */}
              {activeTab === 'path' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">({attackPath.path.length} hops)</span>
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
                </div>
              )}

              {/* Remediation Tab */}
              {activeTab === 'remediation' && (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {attackPath.remediations && attackPath.remediations.length > 0 ? (
                    attackPath.remediations.map((rem: any, idx: number) => (
                      <div key={idx} className="p-3 bg-secondary rounded border border-border space-y-2">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="text-sm font-medium text-foreground">{rem.title}</p>
                            <p className="text-xs text-muted-foreground mt-1">{rem.description}</p>
                          </div>
                          <span className={`text-xs px-2 py-1 rounded whitespace-nowrap ${
                            rem.difficulty === 'low' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                            rem.difficulty === 'medium' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                            'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
                          }`}>
                            {rem.difficulty}
                          </span>
                        </div>
                        <div className="text-xs space-y-1">
                          <p className="text-muted-foreground"><span className="font-medium">Action:</span> {rem.change}</p>
                          <p className="text-muted-foreground"><span className="font-medium">Resource:</span> {rem.target_resource} ({rem.target_resource_type})</p>
                          <p className="text-muted-foreground"><span className="font-medium">Breaks:</span> {rem.impact_count} attack path(s)</p>
                        </div>
                        <div className="bg-muted rounded p-2 font-mono text-xs overflow-x-auto max-h-24 overflow-y-auto">
                          {rem.yaml_snippet}
                        </div>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(rem.yaml_snippet);
                            setCopiedIndex(idx);
                            setTimeout(() => setCopiedIndex(null), 2000);
                          }}
                          className="flex items-center gap-2 text-xs text-primary hover:text-primary/80 transition-colors"
                        >
                          {copiedIndex === idx ? (
                            <>
                              <CheckCircle2 className="w-3 h-3" />
                              Copied
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              Copy YAML
                            </>
                          )}
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-4 text-muted-foreground">
                      <p className="text-sm">No specific remediation suggestions available</p>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-6 text-destructive">
              <p className="font-medium">No attack path found</p>
              <p className="text-xs text-muted-foreground mt-1">Try different source/target nodes</p>
            </div>
          )}
        </div>
      )}

      {!loading && !attackPath && (
        <div className="text-center py-8 text-muted-foreground">
          <Play className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Run analysis to find attack paths</p>
        </div>
      )}
    </div>
  );
}
